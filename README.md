# Начало работы:

### 1 Создать запись в бд - получить ответ


Request GET

`http get url:5000/api/v1/create/project_name.some-branch-name.feature.btc-s.ru/127.0.0.1`

Response

```json
{
    "code": 201,
    "status": "Created",
    "ip": "127.0.0.1",
    "port": 8100,
    "message": "Some text message"
}
```

If data already exists Response would be

```json
{
    "code": 304,
    "status": "Not Modified",
    "ip": "127.0.0.1",
    "port": 8100,
    "message": "Branch already exists on port"
}
```

If params is missing Response would be

```json
{
    "code": 400,
    "status": "Bad Request"
}
```


### 2 Удалить запись, освободить порт - получить ответ

Request DELETE

`http delete localhost:5000/api/v1/delete/project_name.some-branch-name.feature.btc-s.ru/127.0.0.1`

Response

```json
{
    "code": 202,
    "status": "Accepted",
    "message": "Branch remove, current port release"
}
```