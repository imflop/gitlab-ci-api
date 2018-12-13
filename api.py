import os
import json
import redis
import logging
from datetime import datetime
from flask import Flask
from flask_restplus import Api, Resource
from jinja2 import Environment, FileSystemLoader

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FOLDER_NAME = os.path.join(APP_ROOT, 'nginx_configs')
TEMPLATE_FOLDER_NAME = os.path.join(APP_ROOT, 'nginx_templates')
FLAG_FOLDER_NAME = os.path.join(APP_ROOT, 'nginx_flags')

app = Flask(__name__)
app.config.from_envvar('API_SETTINGS')
api = Api(
    app,
    version='0.0.1',
    title='Integration to Gitlab',
    prefix='/api/v1',
    description='A simple giltab integration API',
    doc='/api/swagger'
)
db = redis.StrictRedis(
    host=app.config['REDIS_HOST'],
    port=app.config['REDIS_PORT'],
    db=app.config['REDIS_DB']
)
env = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER_NAME))
logger = logging.getLogger('API')


class DbMixin:

    def is_ip_exists(self, ip: str) -> bool:
        return True if db.exists(ip) else False

    def is_branch_exists(self, branch: str) -> bool:
        return True if db.exists(branch) else False

    def set_ports_to_ip(self, ip: str) -> None:
        ports_dict = {_: True for _ in range(8100, 8300)}
        db.set(ip, json.dumps(ports_dict))

    def set_released_port(self, ip: str, ports: dict) -> None:
        db.set(ip, json.dumps(ports))

    def set_project_meta_to_branch(self, branch: str, data: dict) -> None:
        db.set(branch, json.dumps(data))

    def get_project_meta_by_branch(self, branch: str) -> dict:
        return json.loads(db.get(branch))

    def get_ports_by_ip(self, ip: str) -> dict:
        return json.loads(db.get(ip))

    def get_first_free_port_by_ip(self, ip: str) -> int:
        ports = json.loads(db.get(ip))
        key = [k for k, v in ports.items() if v is True][0]
        ports[key] = False
        db.set(ip, json.dumps(ports))
        return int(key)

    def delete_branch(self, branch: str) -> None:
        db.delete(branch)


class ResponseObject:

    def __init__(self, code: int, status: str, ip: str = None, port: int = None, message: str = None):
        self.code = code
        self.status = status
        self.ip = ip
        self.port = port
        self.message = message

    def as_dict(self):
        return {k: v for k, v in filter(lambda x: x[1] is not None, vars(self).items())}


@api.route('/create/<project>/<ip>')
@api.param('ip', 'The ip address')
@api.param('project', 'Full url of project with branch, for example: project-name.branch-name.feature.site-name.dev')
class Create(Resource, DbMixin):
    def get(self, project=None, ip=None) -> dict:
        """
        Create nginx config from template file by project
        """
        if project and ip:
            raw_data = project.split('.')
            project_name = raw_data[0]
            branch = f'{raw_data[2]}/{raw_data[1]}'

            if not self.is_ip_exists(ip):
                self.set_ports_to_ip(ip)

            if self.is_branch_exists(branch):
                project_data = self.get_project_meta_by_branch(branch)
                # weird
                if 'project_name' not in project_data:
                    project_data.update(project_name=project_name)
                if 'server_name' not in project_data:
                    project_data.update(server_name=project)
                port = project_data['port']
                self._write_data(project_data)
                response = ResponseObject(code=304, status='Not Modified', ip=ip, port=port,
                                          message='Branch already exists on port')
            else:
                port = self.get_first_free_port_by_ip(ip)
                project_data = self._create_project_dict(ip, port, project_name, project)
                self._write_data(project_data)
                self.set_project_meta_to_branch(branch, project_data)
                response = ResponseObject(code=201, status='Created', ip=ip, port=port,
                                          message='New record successfully created')
        else:
            response = ResponseObject(code=400, status='Bad Request')
        return response.as_dict()

    def _create_project_dict(self, ip: int, port: int, project_name: str, project: str) -> dict:
        return dict(
            created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            ip=ip,
            port=port,
            project_name=project_name,
            server_name=project
        )

    def _write_data(self, data: dict) -> None:
        template = env.get_template(f'{data["project_name"]}.tpl')
        conf = template.render(**data)
        filename = f'{data["server_name"].split(".")[0]}.{data["server_name"].split(".")[1]}.conf'

        if not os.path.exists(CONFIG_FOLDER_NAME):
            os.makedirs(CONFIG_FOLDER_NAME)

        with open(f'{CONFIG_FOLDER_NAME}/{filename}', 'w') as f:
            f.write(conf)
            logger.info(f'Config {CONFIG_FOLDER_NAME}/{filename} was created')
            self.__crete_flag_file()

    def __crete_flag_file(self) -> None:
        if not os.path.exists(FLAG_FOLDER_NAME):
            os.makedirs(FLAG_FOLDER_NAME)

        with open(f'{FLAG_FOLDER_NAME}/reload', 'w') as f:
                f.write(str(True))


@api.route('/delete')
class Delete(Resource, DbMixin):
    def delete(self):
        """
        Delete meta data from redis, also change port status
        """
        ip = api.payload.get('ip')
        branch = api.payload.get('branch')
        if self.is_branch_exists(branch) and self.is_ip_exists(ip):
            data = self.get_project_meta_by_branch(branch)
            port = str(data['port'])
            ports = self.get_ports_by_ip(ip)
            ports[port] = True
            self.set_released_port(ip, ports)
            self.delete_branch(branch)
            self._remove_conf(data)
            response = ResponseObject(code=202, status='Accepted', message='Branch remove, current port release')
        else:
            response = ResponseObject(status='Not Found', code=404)
        return response.as_dict()

    def _remove_conf(self, data: dict) -> None:
        filename = f'{data["server_name"].split(".")[0]}.{data["server_name"].split(".")[1]}.conf'
        file_path = f'{CONFIG_FOLDER_NAME}/{filename}'
        if os.path.isfile(file_path):
            os.remove(file_path)


if __name__ == '__main__':
    app.run(
        debug=app.config['DEBUG'],
        host=app.config['SERVER_HOST'],
        port=app.config['SERVER_PORT']
    )
