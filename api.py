import json
import redis
from datetime import datetime
from flask import Flask
from flask_restplus import Api, Resource


app = Flask(__name__)
api = Api(app)
db = redis.StrictRedis(host='localhost', port=6379, db=1)


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
        return json.dumps(db.get(ip))

    def get_first_free_port_by_ip(self, ip: str) -> int:
        ports = json.loads(db.get(ip))
        key = [k for k, v in ports.items() if v is True][0]
        ports[key] = False
        db.set(ip, json.dumps(ports))
        return int(key)

    def delete_branch(self, branch: str) -> None:
        db.delete(branch)


@api.route('/api/v1/create/<project>/<ip>')
class Create(Resource, DbMixin):
    def get(self, project, ip) -> dict:
        if project and ip:
            raw_data = project.split('.')
            project_name = raw_data[0]
            branch = f'{raw_data[2]}/{raw_data[1]}'
            if self.is_ip_exists(ip):
                if self.is_branch_exists(branch):
                    project_data = self.get_project_meta_by_branch(branch)
                    port = project_data['port']
                    response = ResponseObject(code=304, status='Not Modified', ip=ip, port=port,
                                              message='Branch already exists on current port')
                else:
                    port = self.get_first_free_port_by_ip(ip)
                    project_data = self._create_project_dict(ip, port, project_name)
                    self.set_project_meta_to_branch(branch, project_data)
                    response = ResponseObject(code=201, status='Created', ip=ip, port=port,
                                              message='New record successfully created')
            else:
                self.set_ports_to_ip(ip)
                port = self.get_first_free_port_by_ip(ip)
                project_data = self._create_project_dict(ip, port, project_name)
                self.set_project_meta_to_branch(branch, project_data)
                response = ResponseObject(code=201, status='Created', ip=ip, port=port,
                                          message='New record successfully created')
        else:
            response = ResponseObject(code=404, status='Not Found')
        return response.as_dict()

    def _create_project_dict(self, ip: int, port: int, project_name: str) -> dict:
        return dict(
            created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            ip=ip,
            port=port,
            project_name=project_name
        )


@api.route('/api/v1/delete')
class Delete(Resource, DbMixin):
    def delete(self):
        """
        Delete meta data from redis, also change port status
        :return: 204 if exists else 404
        """
        ip = api.payload.get('ip')
        branch = api.payload.get('branch')
        if self.is_branch_exists(branch) and self.is_ip_exists(ip):
            data = self.get_project_meta_by_branch(branch)
            port = data['port']
            ports = self.get_ports_by_ip(ip)
            ports[port] = True
            self.set_released_port(ip, ports)
            self.delete_branch(branch)
            response = ResponseObject(code=202, status='Accepted', message='Branch remove, current port release')
        else:
            response = ResponseObject(status='Not Found', code=404)
        return response.as_dict()


class ResponseObject:

    def __init__(self, code: int, status: str, ip: str = None, port: int = None, message: str = None):
        self.code = code
        self.status = status
        self.ip = ip
        self.port = port
        self.message = message

    def as_dict(self):
        return {k: v for k, v in filter(lambda x: x[1] is not None, vars(self).items())}


if __name__ == '__main__':
    app.run(debug=True)
