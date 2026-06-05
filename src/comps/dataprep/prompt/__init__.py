# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pkgutil
import importlib

def auto_load_prompts():
    package_name = __name__  # "prompt"

    for _, module_name, _ in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{package_name}.{module_name}")