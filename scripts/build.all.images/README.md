# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

To build all EKBA components images:
```docker compose build```

To build a single service's image:
```docker compose build embedding```

To build extra service's image for special purpose:
```docker compose -f docker-compose.extra.yaml build <service>```

Note: When building images of ekba-ui and ekba-ui-mini, might be blocked by the missing .env/.env.mini
files, it means the developer need to prepare them under ../../src/ui/ directory.

Note: if your building environment is inside a proxy-required network, maybe you need to specify the
proxy args in command line, like
```docker compose build --build-arg http_proxy=$http_proxy ... ...```
