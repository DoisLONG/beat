# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

# MONGO configuration
MONGO_HOST = os.getenv("MONGO_HOST", "10.3.70.118")
MONGO_PORT = os.getenv("MONGO_PORT", 27017)
DB_NAME = os.getenv("MONGO_DB_NAME", "OPEA_EAP")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "ChatHistory")
USER_LOGS_COLLECTION_NAME = os.getenv("USER_LOGS_COLLECTION_NAME", "UserLogs")
