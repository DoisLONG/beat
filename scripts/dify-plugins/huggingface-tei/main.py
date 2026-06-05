# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from dify_plugin import Plugin, DifyPluginEnv

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))

if __name__ == "__main__":
    plugin.run()
