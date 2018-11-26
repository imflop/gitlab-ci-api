import json
import redis
from datetime import datetime
from flask import Flask
from flask_restplus import Api, Resource


app = Flask(__name__)
api = Api(app)
db = redis.StrictRedis(host='localhost', port=6379, db=1)


@api.route('/api/v1/status/<branch>')
class Status(Resource):
    def get(self, branch):
        """
        Api status (not now)
        :return: Dummy status
        """
        if branch:
            if db.exists(branch):
                data = db.get(branch)
                return dict(branch=branch, meta=json.loads(data), code=200, status='OK')
        else:
            return dict(status='Not Found', code=404)


@api.route('/api/v1/create')
class Create(Resource):
    def post(self) -> dict:
        branch = api.payload.get('branch')
        ip = api.payload.get('ip')
        if self._is_ip_exists(ip):
            if self._is_branch_exists(branch):
                project_data = self._get_project_meta_by_branch_name(branch)
                port = project_data['port']
                return self.response_dict(code=304, status='Not Modified', ip=ip, port=port,
                                          message='Branch already exists on current port')
            else:
                port = self._get_first_free_port_by_ip(ip)
                project_data = dict(
                    created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    ip=ip,
                    port=port
                )
                self._set_project_meta_to_branch(branch, project_data)
                return self.response_dict(code=201, status='Created', ip=ip, port=port, message='OK')
        else:
            self._set_ports_to_ip(ip)
            port = self._get_first_free_port_by_ip(ip)
            project_data = dict(
                created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                ip=ip,
                port=port
            )
            self._set_project_meta_to_branch(branch, project_data)
            return self.response_dict(code=201, status='Created', ip=ip, port=port, message='OK')

    def _is_ip_exists(self, ip: str) -> bool:
        return True if db.exists(ip) else False

    def _is_branch_exists(self, branch: str) -> bool:
        return True if db.exists(branch) else False

    def _set_ports_to_ip(self, ip: str) -> bool:
        ports_dict = {_: True for _ in range(8100, 8300)}
        return db.set(ip, json.dumps(ports_dict))

    def _set_project_meta_to_branch(self, branch: str, data: dict) -> None:
        db.set(branch, json.dumps(data))

    def _get_project_meta_by_branch_name(self, branch: str) -> dict:
        d = db.get(branch)
        return json.loads(d)

    def _get_project_data_by_ip(self, ip: str) -> dict:
        d = db.get(ip)
        return json.loads(d)

    def _get_first_free_port_by_ip(self, ip: str) -> int:
        ports = json.loads(db.get(ip))
        key = [k for k, v in ports.items() if v is True][0]
        ports[key] = False
        db.set(ip, json.dumps(ports))
        return int(key)

    def response_dict(self, code: int, status: str, ip: str, port: int, message: str) -> dict:
        return dict(code=code, status=status, ip=ip, port=port, message=message)


@api.route('/api/v1/delete/<project_name>')
class Delete(Resource):
    def delete(self, project_name):
        """
        Delete project from redis
        :param project_name: string name of project
        :return: 204 if exists else 404
        """
        if db.exists(project_name):
            db.delete(project_name)
            return dict(status='Accepted', code=202)
        else:
            return dict(status='Not Found', code=404)


def _get_rnd_port() -> int:
    from random import randint
    return randint(1025, 65535)


if __name__ == '__main__':
    app.run(debug=True)
