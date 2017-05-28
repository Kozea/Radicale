---
layout: page
title: Reverse Proxy
permalink: /proxy/
---

When a everse proxy is used, the path at which Radicale is available must
be provided via the `X-Script-Name` header.


Example **nginx** configuration:
```nginx
location /sub/folder/radicale {
    proxy_pass localhost:5232/; # The / is important!
    proxy_set_header X-Script-Name /sub/folder/radicale;
}
```

Be reminded that Radicale's default configuration enforces limits on the
maximum number of parallel connections, the maximum file size and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.
