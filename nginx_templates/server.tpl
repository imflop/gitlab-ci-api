server {
    listen 80;
    server_name {{ server_name }};

    location / {
        proxy_pass http://{{ ip }}:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}