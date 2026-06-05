# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from dify_plugin import Plugin, DifyPluginEnv

plugin = Plugin(DifyPluginEnv())

if __name__ == "__main__":
    plugin.run()
