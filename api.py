import json
import redis
from datetime import datetime
from flask import Flask
from flask_restplus import Api, Resource


app = Flask(__name__)
api = Api(app)
db = redis.StrictRedis(host='localhost', port=6379, db=1)


@api.route('/api/v1/create')
class Create(Resource):
    def post(self) -> dict:
        branch = api.payload.get('branch')
        ip = api.payload.get('ip')
        if Utils.is_ip_exists(ip):
            if Utils.is_branch_exists(branch):
                project_data = Utils.get_project_meta_by_branch(branch)
                port = project_data['port']
                return Utils.response_dict(code=304, status='Not Modified', ip=ip, port=port,
                                           message='Branch already exists on current port')
            else:
                port = Utils.get_first_free_port_by_ip(ip)
                project_data = dict(
                    created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    ip=ip,
                    port=port
                )
                Utils.set_project_meta_to_branch(branch, project_data)
                return Utils.response_dict(code=201, status='Created', ip=ip, port=port, message='OK')
        else:
            Utils.set_ports_to_ip(ip)
            port = Utils.get_first_free_port_by_ip(ip)
            project_data = dict(
                created_at=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                ip=ip,
                port=port
            )
            Utils.set_project_meta_to_branch(branch, project_data)
            return Utils.response_dict(code=201, status='Created', ip=ip, port=port, message='OK')


@api.route('/api/v1/delete')
class Delete(Resource):
    def delete(self):
        """
        Delete meta data from redis, also change port status
        :return: 204 if exists else 404
        """
        ip = api.payload.get('ip')
        branch = api.payload.get('branch')
        if Utils.is_branch_exists(branch) and Utils.is_ip_exists(ip):
            data = Utils.get_project_meta_by_branch(branch)
            port = data['port']
            ports = Utils.get_ports_by_ip(ip)
            ports[port] = True
            Utils.set_release_port(ip, ports)
            db.delete(branch)
            return Utils.response_dict(code=202, status='Accepted', ip=ip, port=port,
                                       message='Branch remove, current port release')
        else:
            return Utils.response_dict(status='Not Found', code=404)


class Utils:
    @staticmethod
    def response_dict(code: int, status: str, ip=None, port=None, message=None) -> dict:
        if not ip and not port and not message:
            return dict(code=code, status=status)
        else:
            return dict(code=code, status=status, ip=ip, port=port, message=message)

    @staticmethod
    def is_ip_exists(ip: str) -> bool:
        return True if db.exists(ip) else False

    @staticmethod
    def is_branch_exists(branch: str) -> bool:
        return True if db.exists(branch) else False

    @staticmethod
    def set_ports_to_ip(ip: str) -> None:
        ports_dict = {_: True for _ in range(8100, 8300)}
        db.set(ip, json.dumps(ports_dict))

    @staticmethod
    def set_release_port(ip: str, ports: dict) -> None:
        db.set(ip, json.dumps(ports))

    @staticmethod
    def set_project_meta_to_branch(branch: str, data: dict) -> None:
        db.set(branch, json.dumps(data))

    @staticmethod
    def get_project_meta_by_branch(branch: str) -> dict:
        return json.loads(db.get(branch))

    @staticmethod
    def get_ports_by_ip(ip: str) -> dict:
        return json.loads(db.get(ip))

    @staticmethod
    def get_first_free_port_by_ip(ip: str) -> int:
        ports = json.loads(db.get(ip))
        key = [k for k, v in ports.items() if v is True][0]
        ports[key] = False
        db.set(ip, json.dumps(ports))
        return int(key)


if __name__ == '__main__':
    app.run(debug=True)
