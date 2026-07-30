CREATE DATABASE IF NOT EXISTS ekba_kb;
USE ekba_kb;

CREATE TABLE `sp_sop_info` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `filename` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_uri` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `task_status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `position_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sop_version` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `num_flag` int NOT NULL DEFAULT '0',
  `file_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `percent` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '0%',
  `lang` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tenant_id` int DEFAULT NULL COMMENT '租户ID',
  `start_time` date DEFAULT NULL COMMENT 'SOP 生效时间',
  `end_time` date DEFAULT NULL COMMENT 'SOP 到期时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_sop_time_range` (`tenant_id`,`start_time`,`end_time`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS `sp_user` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `full_name` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `avatar_url` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role_id` int NOT NULL DEFAULT '3',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `telephone` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `department_id` int DEFAULT NULL,
  `position_id` int DEFAULT NULL,
  `last_login_at` timestamp NULL DEFAULT NULL,
  `last_login_ip` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `welcome_guide_pending` int NOT NULL DEFAULT '0' COMMENT '0=第一次登录,1=非第一次登录',
  `dashboard_welcome_guide_pending` int NOT NULL DEFAULT '0' COMMENT '0=仪表第一次登录,1=仪表非第一次登录',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` int DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `updated_by` int DEFAULT NULL,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `deleted_by` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_users_name` (`name`),
  KEY `idx_users_email` (`email`),
  KEY `idx_users_active` (`is_active`),
  UNIQUE KEY `uk_user_tenant_name` (`tenant_id`,`name`) USING BTREE COMMENT '同一租户内用户名唯一',
  UNIQUE KEY `uk_user_tenant_email` (`tenant_id`,`email`) USING BTREE COMMENT '同一租户内邮箱唯一'
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sp_sop_version` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '版本ID，主键',
  `file_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件名',
  `version_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '版本号，如：v1.0.0',
  `version_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '版本名称',
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '版本内容',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `sop_info_id` int DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_file_name` (`file_name`) USING BTREE,
  KEY `idx_created_at` (`created_at`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SOP版本管理表';

CREATE TABLE IF NOT EXISTS `sp_position` (
  `position_id` int NOT NULL AUTO_INCREMENT COMMENT '岗位ID（主键）',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `department_id` int NOT NULL COMMENT '所属部门ID（外键）',
  `position_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '岗位名称',
  `duty` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '岗位职责',
  `requirement` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '任职要求',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '备注信息',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`position_id`) USING BTREE,
  UNIQUE KEY `uk_post_dept` (`department_id`,`position_name`) USING BTREE COMMENT '同一部门内岗位名称唯一'
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='岗位信息表';

CREATE TABLE IF NOT EXISTS `sp_department` (
  `department_id` int NOT NULL AUTO_INCREMENT COMMENT '部门ID（主键）',
  `company_id` int NOT NULL COMMENT '所属公司ID（外键）',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `department_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '部门名称',
  `manager` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '部门负责人',
  `manager_phone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '负责人电话',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '备注信息',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`department_id`) USING BTREE,
  UNIQUE KEY `uk_dept_company` (`company_id`,`department_name`) USING BTREE COMMENT '同一公司内部门名称唯一'
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部门信息表';

CREATE TABLE IF NOT EXISTS `sp_company` (
  `company_id` int NOT NULL AUTO_INCREMENT COMMENT '公司ID（主键）',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `company_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '公司名称',
  `establish_time` date DEFAULT NULL COMMENT '成立时间',
  `address` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '公司地址',
  `contact_phone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '联系电话',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '备注信息',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`company_id`) USING BTREE,
  UNIQUE KEY `uk_company_name` (`company_name`) USING BTREE COMMENT '公司名称唯一'
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='公司信息表';

CREATE TABLE IF NOT EXISTS `sp_exam_record` (
  `id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '考试ID',
  `user_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户ID',
  `position_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '岗位ID',
  `start_time` datetime DEFAULT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `exam_category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '考试类型',
  `filename` varchar(255) DEFAULT NULL COMMENT '文件名（混合出题为岗位id）',
  `conversation_id` varchar(255) DEFAULT NULL COMMENT 'dfxw会话ID',
  `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT '总结',
  `total_score` float(10,2) DEFAULT NULL COMMENT '总分',
  `accumulated_score` float(10,2) DEFAULT NULL COMMENT '考试得分',
  `total_questions` int DEFAULT NULL COMMENT '总题数',
  `answered_questions` int DEFAULT NULL COMMENT '答题数',
  `sop_id` int DEFAULT NULL COMMENT 'sop_id,如果为空，那么为岗位混合答题',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `sp_course_progress`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `user_id` int(0) NOT NULL COMMENT '用户ID',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `video_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `course_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '课程ID',
  `watched_seconds` int(0) NULL DEFAULT 0 COMMENT '已观看时长（秒）',
  `progress_percent` decimal(5, 2) NULL DEFAULT 0.00 COMMENT '进度百分比',
  `last_position` int(0) NULL DEFAULT 0 COMMENT '上次播放位置（秒）',
  `is_completed` tinyint(1) NULL DEFAULT 0 COMMENT '是否已完成',
  `last_learn_time` datetime(0) NULL DEFAULT NULL COMMENT '最近学习时间',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id`) USING BTREE,
  INDEX `idx_course_id`(`course_id`) USING BTREE,
  INDEX `idx_user_course`(`user_id`, `course_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '课程学习进度表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_learning_record`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '学习会话ID',
  `user_id` int(0) NOT NULL COMMENT '用户ID',
  `course_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '课程ID',
  `video_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '视频ID',
  `start_time` datetime(0) NOT NULL COMMENT '开始时间',
  `end_time` datetime(0) NULL DEFAULT NULL COMMENT '结束时间',
  `watch_seconds` int(0) NULL DEFAULT 0 COMMENT '本次观看时长（秒）',
  `start_position` int(0) NULL DEFAULT 0 COMMENT '开始播放位置（秒）',
  `end_position` int(0) NULL DEFAULT 0 COMMENT '结束播放位置（秒）',
  `is_completed` tinyint(1) NULL DEFAULT 0 COMMENT '是否完整看完（0:否，1:是）',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `from_position` int(0) NULL DEFAULT 0 COMMENT '开始播放位置（秒）',
  `watch_progress` decimal(5, 2) NULL DEFAULT 0.00 COMMENT '观看进度百分比',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id`) USING BTREE,
  INDEX `idx_course_id`(`course_id`) USING BTREE,
  INDEX `idx_video_id`(`video_id`) USING BTREE,
  INDEX `idx_session_id`(`session_id`) USING BTREE,
  INDEX `idx_start_time`(`start_time`) USING BTREE,
  INDEX `idx_user_course_video`(`user_id`, `course_id`, `video_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 8 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '学习记录表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_user_learning_summary`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `user_id` int(0) NOT NULL COMMENT '用户ID',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `total_watch_seconds` bigint(0) NULL DEFAULT 0 COMMENT '总观看时长（秒）',
  `today_watch_seconds` int(0) NULL DEFAULT 0 COMMENT '今日观看时长（秒）',
  `total_video_count` int(0) NULL DEFAULT 0 COMMENT '观看过的视频总数',
  `total_course_count` int(0) NULL DEFAULT 0 COMMENT '学习的课程总数',
  `last_learn_time` datetime(0) NULL DEFAULT NULL COMMENT '最近学习时间',
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '用户学习汇总表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_course`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `course_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '课程唯一标识',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '课程标题',
  `code` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '课程编码',
  `category` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '分类',
  `cover_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '封面图URL',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '课程描述',
  `tags` json NULL COMMENT '标签数组',
  `status` enum('draft','published','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'draft' COMMENT '状态',
  `video_count` int(0) NULL DEFAULT 0 COMMENT '视频数量',
  `total_duration` int(0) NULL DEFAULT 0 COMMENT '总时长（秒）',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `is_deleted` tinyint(1) NULL DEFAULT 0 COMMENT '是否已删除（逻辑删除）',
  `keywordslist` json NULL COMMENT '关键词列表（JSON数组格式）',
  `position_id` int(0) NULL DEFAULT NULL COMMENT '关联岗位ID',
  `version_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'v1' COMMENT '版本号',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_status`(`status`) USING BTREE,
  INDEX `idx_category`(`category`) USING BTREE,
  INDEX `idx_code`(`code`) USING BTREE,
  INDEX `idx_course_id`(`course_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 12 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '课程表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_material`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `material_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '资料唯一标识',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '资料名称',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '说明',
  `category` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '分类',
  `course_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '关联课程ID',
  `file_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '文件类型（pdf/ppt/doc/xlsx等）',
  `file_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '文件URL',
  `size` bigint(0) NULL DEFAULT NULL COMMENT '文件大小（字节）',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `position_id` int(0) NULL DEFAULT NULL COMMENT '关联岗位ID',
  `is_deleted` tinyint(1) NULL DEFAULT 0 COMMENT '是否已删除（逻辑删除）',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_course_id`(`course_id`) USING BTREE,
  INDEX `idx_category`(`category`) USING BTREE,
  INDEX `idx_file_type`(`file_type`) USING BTREE,
  INDEX `idx_material_id`(`material_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 8 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '学习资料表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_video`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `video_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '视频唯一标识',
  `course_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '所属课程ID',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '视频标题',
  `video_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '视频URL',
  `duration` int(0) NOT NULL COMMENT '视频时长（秒）',
  `order_index` int(0) NULL DEFAULT 1 COMMENT '播放顺序',
  `created_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` datetime(0) NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_course_id`(`course_id`) USING BTREE,
  INDEX `idx_video_id`(`video_id`) USING BTREE,
  INDEX `idx_order`(`order_index`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 10 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '视频表' ROW_FORMAT = Dynamic;

CREATE TABLE IF NOT EXISTS `sp_tenant`  (
  `tenant_id` int(0) NOT NULL AUTO_INCREMENT COMMENT '租户ID（主键）',
  `tenant_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '租户编码（唯一）',
  `tenant_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '租户名称',
  `status` tinyint(0) NOT NULL DEFAULT 1 COMMENT '状态：1-启用，0-停用',
  `expire_time` datetime(0) NULL DEFAULT NULL COMMENT '过期时间',
  `max_user_count` int(0) NULL DEFAULT NULL COMMENT '最大用户数',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注信息',
  `create_time` datetime(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) COMMENT '记录创建时间',
  `update_time` datetime(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0) COMMENT '记录更新时间',
  PRIMARY KEY (`tenant_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '租户信息表' ROW_FORMAT = Dynamic;

-- 用户会话表
CREATE TABLE IF NOT EXISTS `sp_user_session` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会话ID',
  `user_id` int NOT NULL COMMENT '用户ID',
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `login_time` datetime NOT NULL COMMENT '登录时间',
  `last_active_time` datetime NOT NULL COMMENT '最后活跃时间',
  `logout_time` datetime DEFAULT NULL COMMENT '登出时间',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_tenant_id` (`tenant_id`),
  KEY `idx_login_time` (`login_time`),
  KEY `idx_logout_time` (`logout_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户会话表';

-- Dashboard 统计快照表（用于历史数据对比）
CREATE TABLE IF NOT EXISTS `sp_dashboard_statistics` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `period_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '周期类型：day/week/month',
  `period_start` date NOT NULL COMMENT '周期开始日期',
  `period_end` date NOT NULL COMMENT '周期结束日期',
  `total_users` int DEFAULT 0 COMMENT '总用户数',
  `active_users` int DEFAULT 0 COMMENT '活跃用户数',
  `total_learn_seconds` bigint DEFAULT 0 COMMENT '总学习时长（秒）',
  `avg_pass_rate` float DEFAULT 0.0 COMMENT '平均达标率',
  `exam_count` int DEFAULT 0 COMMENT '考试场次',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tenant_period` (`tenant_id`,`period_type`,`period_start`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Dashboard统计快照表';

CREATE TABLE `sp_sop_leaderboard` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `sop_id` INT NOT NULL COMMENT 'SOP ID',
    `user_id` INT NOT NULL COMMENT '用户ID',
    `tenant_id` INT NOT NULL COMMENT '租户ID',
    `rank` INT NOT NULL COMMENT '当前名次',
    `score` FLOAT NOT NULL DEFAULT 0.0 COMMENT '当前分数',
    `last_rank` INT DEFAULT NULL COMMENT '上一次名次，NULL 表示新上榜',
    `rank_change` INT DEFAULT 0 COMMENT '名次变动 = last_rank - rank，正数升名次，负数降名次，NULL 表示新上榜',
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '排行榜最后更新时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次上榜时间',

    INDEX `idx_sop_id` (`sop_id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SOP 排行榜表 - 持久化存储每个 SOP 的用户排名快照，支持名次变化追踪';
-- 用户日活统计表 (用于Dashboard热力图)
CREATE TABLE IF NOT EXISTS `sp_user_activity` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `tenant_id` int NOT NULL COMMENT '租户ID',
  `stat_date` date NOT NULL COMMENT '统计日期',
  `active_users` int DEFAULT 0 COMMENT '日活跃用户数',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `_tenant_date_uc` (`tenant_id`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户日活统计表';

-- ============================================================================
-- 模型配置管理模块 - 数据库初始化脚本
-- 创建时间：2026-03-19
-- 说明：包含模型配置的当前配置、历史版本和连通性测试记录三张表
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 当前激活的模型配置表 (sp_model_config_current)
-- 用途：存储各业务场景正在使用的模型配置，每个 scope 仅一条记录
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sp_model_config_current` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    `scope` VARCHAR(64) NOT NULL COMMENT '全局模型配置作用域',
    `provider` VARCHAR(128) NULL COMMENT '模型服务提供商',
    `model` VARCHAR(256) NOT NULL COMMENT '模型名称',
    `transport` VARCHAR(16) NOT NULL DEFAULT 'http' COMMENT '模型接入方式',
    `base_url` VARCHAR(1024) NULL COMMENT '模型服务地址',
    `runtime_options_json` TEXT NULL COMMENT '本地运行时配置 JSON',
    `secret_encrypted` TEXT NULL COMMENT '加密后的密钥，不保存明文',
    `secret_key_id` VARCHAR(256) NULL COMMENT '密钥管理系统标识',
    `version` INT NOT NULL DEFAULT 1 COMMENT '配置版本',
    `last_test_status` VARCHAR(32) NULL COMMENT '最近连通性测试状态',
    `last_tested_at` DATETIME NULL COMMENT '最近连通性测试时间',
    `last_test_error` TEXT NULL COMMENT '最近测试错误',
    `activated_by` VARCHAR(128) NULL COMMENT '激活操作者',
    `activated_at` DATETIME NULL COMMENT '激活时间',
    `is_active` TINYINT NOT NULL DEFAULT 1 COMMENT '是否当前激活',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY `uq_model_config_current_scope` (`scope`),
    CONSTRAINT `ck_model_config_current_scope` CHECK (`scope` IN ('dataprep_llm', 'smart_practice_llm', 'embedding', 'asr')),
    CONSTRAINT `ck_model_config_current_transport` CHECK (`transport` IN ('http', 'local')),
    CONSTRAINT `ck_model_config_current_is_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='当前激活的模型配置表';

-- 为 scope 字段添加索引以提升查询性能
CREATE INDEX `idx_scope_current` ON `sp_model_config_current` (`scope`);


-- ----------------------------------------------------------------------------
-- 2. 模型配置历史版本表 (sp_model_config_revision)
-- 用途：每次配置变更时自动创建历史记录，支持版本回滚和审计追踪
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sp_model_config_revision` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    `scope` VARCHAR(64) NOT NULL COMMENT '全局模型配置作用域',
    `provider` VARCHAR(128) NULL COMMENT '模型服务提供商',
    `model` VARCHAR(256) NOT NULL COMMENT '模型名称',
    `transport` VARCHAR(16) NOT NULL DEFAULT 'http' COMMENT '模型接入方式',
    `base_url` VARCHAR(1024) NULL COMMENT '模型服务地址',
    `runtime_options_json` TEXT NULL COMMENT '本地运行时配置 JSON',
    `secret_encrypted` TEXT NULL COMMENT '加密后的密钥',
    `secret_key_id` VARCHAR(256) NULL COMMENT '密钥管理系统标识',
    `version` INT NOT NULL COMMENT '版本号',
    `last_test_status` VARCHAR(32) NULL COMMENT '测试状态',
    `last_tested_at` DATETIME NULL COMMENT '测试时间',
    `last_test_error` TEXT NULL COMMENT '测试错误',
    `activated_by` VARCHAR(128) NULL COMMENT '激活操作者',
    `activated_at` DATETIME NULL COMMENT '激活时间',
    `changed_by` VARCHAR(128) NULL COMMENT '修改操作者',
    `change_reason` VARCHAR(512) NULL COMMENT '变更原因',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    UNIQUE KEY `uq_model_config_revision_scope_version` (`scope`, `version`),
    CONSTRAINT `ck_model_config_revision_scope` CHECK (`scope` IN ('dataprep_llm', 'smart_practice_llm', 'embedding', 'asr')),
    CONSTRAINT `ck_model_config_revision_transport` CHECK (`transport` IN ('http', 'local'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型配置历史版本表';

-- 为 scope 字段添加索引以提升查询性能
CREATE INDEX `idx_scope_revision` ON `sp_model_config_revision` (`scope`);


-- ----------------------------------------------------------------------------
-- 3. 模型连通性测试记录表 (sp_model_connectivity_check)
-- 用途：记录每次手动或自动触发的连通性测试结果，用于健康检查和故障诊断
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sp_model_connectivity_check` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    `scope` VARCHAR(64) NOT NULL COMMENT '全局模型配置作用域',
    `provider` VARCHAR(128) NULL COMMENT '测试时提供商',
    `model` VARCHAR(256) NOT NULL COMMENT '测试时模型',
    `base_url` VARCHAR(1024) NULL COMMENT '测试时地址',
    `version` INT NOT NULL COMMENT '测试对应配置版本',
    `trigger_type` VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '测试触发方式',
    `status` VARCHAR(32) NOT NULL COMMENT '测试状态',
    `latency_ms` INT NULL COMMENT '请求时延（毫秒）',
    `error_message` TEXT NULL COMMENT '错误描述',
    `metadata_json` TEXT NULL COMMENT '测试元数据 JSON',
    `checked_by` VARCHAR(128) NULL COMMENT '测试执行者',
    `checked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '测试时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    CONSTRAINT `ck_model_connectivity_check_scope` CHECK (`scope` IN ('dataprep_llm', 'smart_practice_llm', 'embedding', 'asr')),
    CONSTRAINT `ck_model_connectivity_check_status` CHECK (`status` IN ('success', 'failed', 'timeout', 'skipped'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型连通性测试记录表';

-- 为 scope 字段添加索引以提升查询性能
CREATE INDEX `idx_scope_check` ON `sp_model_connectivity_check` (`scope`);


-- ----------------------------------------------------------------------------
-- 4. 客户端版本发布表 (sp_app_version)
-- 用途：客户端热更新版本管理（第一期最简版）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sp_app_version` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `edition_name` VARCHAR(64) NOT NULL COMMENT '版本名称（展示用）',
    `edition_version_code` INT NOT NULL COMMENT '版本号（程序比较用）',
    `describe_zh` TEXT NULL COMMENT '中文更新说明',
    `describe_en` TEXT NULL COMMENT '英文更新说明',
    `describe_th` TEXT NULL COMMENT '泰文更新说明',
    `edition_url` VARCHAR(1024) NOT NULL COMMENT '安装包或wgt下载地址',
    `edition_force` TINYINT NOT NULL DEFAULT 0 COMMENT '是否强制更新：0否1是',
    `package_type` TINYINT NOT NULL DEFAULT 1 COMMENT '包类型：0整包 1wgt',
    `edition_issue` TINYINT NOT NULL DEFAULT 1 COMMENT '是否发行：0否1是',
    `edition_silence` TINYINT NOT NULL DEFAULT 0 COMMENT '是否静默更新：0否1是',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1已发布 2已撤销',
    `published_at` DATETIME NULL COMMENT '发布时间',
    `published_by` VARCHAR(64) NULL COMMENT '发布人',
    `revoked_at` DATETIME NULL COMMENT '撤销时间',
    `revoked_by` VARCHAR(64) NULL COMMENT '撤销人',
    `revoke_reason` VARCHAR(255) NULL COMMENT '撤销原因',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_edition_version_code` (`edition_version_code`),
    KEY `idx_current_release` (`status`, `edition_issue`, `edition_version_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户端版本发布表（最简版）';



-- 配置认证方式
ALTER USER 'root'@'%' IDENTIFIED WITH caching_sha2_password BY 'Eap@dfxw2025';
SET GLOBAL authentication_policy = 'caching_sha2_password';
FLUSH PRIVILEGES;


-- 插入租户数据
-- INSERT INTO `sp_tenant` (
--   `tenant_id`,
--   `tenant_code`,
--   `tenant_name`,
--   `status`,
--   `expire_time`,
--   `max_user_count`,
--   `remark`,
--   `create_time`,
--   `update_time`
-- ) VALUES (
--   1,
--   'general_tenant',
--   '通用租户',
--   1,
--   NULL,
--   1000,
--   '系统默认租户',
--   CURRENT_TIMESTAMP,
--   CURRENT_TIMESTAMP
-- );

-- 插入用户数据
-- INSERT INTO `sp_user` (
--   `id`,
--   `name`,
--   `email`,
--   `full_name`,
--   `password`,
--   `avatar_url`,
--   `role_id`,
--   `tenant_id`,
--   `is_active`,
--   `telephone`,
--   `company_id`,
--   `department_id`,
--   `position_id`,
--   `last_login_at`,
--   `last_login_ip`,
--   `created_at`,
--   `created_by`,
--   `updated_at`,
--   `updated_by`,
--   `deleted_at`,
--   `deleted_by`
-- ) VALUES (
--   1,
--   'superadmin',
--   'superadmin@example.com',
--   '超级管理员',
--   '$2b$12$2TvYzzmwaC.kgq7xUa8XkeRlUU.aL3SkPzawOZTEZzeqpg6RcSj/m',
--   NULL,
--   1,  -- 假设1为最高权限角色
--   1,  -- 对应通用租户
--   1,
--   NULL,
--   NULL,
--   NULL,
--   NULL,
--   NULL,
--   NULL,
--   CURRENT_TIMESTAMP,
--   NULL,
--   CURRENT_TIMESTAMP,
--   NULL,
--   NULL,
--   NULL
-- );


-- =============================================================================
-- 业务多语种改造初始化 SQL
-- 规则：zh 复用原表（无后缀）；en / th 新建后缀表
-- 说明：仅包含可执行 DDL/DML；接口人工触发步骤不放入 init 脚本
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. sp_user 新增 lang 字段
-- -----------------------------------------------------------------------------
ALTER TABLE sp_user
    ADD COLUMN lang VARCHAR(8) NOT NULL DEFAULT 'zh'
        COMMENT '业务语种环境（zh/en/th）';

-- -----------------------------------------------------------------------------
-- 1.1 内置默认租户与超级管理员账号
-- 说明：与 /v1/auth/register 保持一致，默认创建 tenant_id=1 的 OWNER 用户
-- 默认密码明文：12345678
-- -----------------------------------------------------------------------------
INSERT INTO `sp_tenant` (
    `tenant_id`,
    `tenant_code`,
    `tenant_name`,
    `status`,
    `expire_time`,
    `max_user_count`,
    `remark`,
    `create_time`,
    `update_time`
) VALUES (
    1,
    'general_tenant',
    '通用租户',
    1,
    NULL,
    1000,
    '系统默认租户',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON DUPLICATE KEY UPDATE
    `tenant_code` = VALUES(`tenant_code`),
    `tenant_name` = VALUES(`tenant_name`),
    `status` = VALUES(`status`),
    `expire_time` = VALUES(`expire_time`),
    `max_user_count` = VALUES(`max_user_count`),
    `remark` = VALUES(`remark`),
    `update_time` = CURRENT_TIMESTAMP;

INSERT INTO `sp_user` (
    `name`,
    `email`,
    `full_name`,
    `password`,
    `avatar_url`,
    `role_id`,
    `tenant_id`,
    `is_active`,
    `telephone`,
    `company_id`,
    `department_id`,
    `position_id`,
    `last_login_at`,
    `last_login_ip`,
    `welcome_guide_pending`,
    `dashboard_welcome_guide_pending`,
    `created_at`,
    `created_by`,
    `updated_at`,
    `updated_by`,
    `deleted_at`,
    `deleted_by`,
    `lang`
) VALUES
    (
        'superadmin',
        'superadmin@example.com',
        NULL,
        '$2y$12$G8IGl1se63FWh082fO7nOO2Ax9MfucHK.RAZPOzIjTIHt.sBlipEK',
        NULL,
        1,
        1,
        1,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        0,
        0,
        CURRENT_TIMESTAMP,
        NULL,
        CURRENT_TIMESTAMP,
        NULL,
        NULL,
        NULL,
        'zh'
    ),
    (
        'superadmin_en',
        'superadmin_en@example.com',
        NULL,
        '$2y$12$G8IGl1se63FWh082fO7nOO2Ax9MfucHK.RAZPOzIjTIHt.sBlipEK',
        NULL,
        1,
        1,
        1,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        0,
        0,
        CURRENT_TIMESTAMP,
        NULL,
        CURRENT_TIMESTAMP,
        NULL,
        NULL,
        NULL,
        'en'
    ),
    (
        'superadmin_th',
        'superadmin_th@example.com',
        NULL,
        '$2y$12$G8IGl1se63FWh082fO7nOO2Ax9MfucHK.RAZPOzIjTIHt.sBlipEK',
        NULL,
        1,
        1,
        1,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        0,
        0,
        CURRENT_TIMESTAMP,
        NULL,
        CURRENT_TIMESTAMP,
        NULL,
        NULL,
        NULL,
        'th'
    )
ON DUPLICATE KEY UPDATE
    `password` = VALUES(`password`),
    `role_id` = VALUES(`role_id`),
    `tenant_id` = VALUES(`tenant_id`),
    `is_active` = VALUES(`is_active`),
    `welcome_guide_pending` = VALUES(`welcome_guide_pending`),
    `dashboard_welcome_guide_pending` = VALUES(`dashboard_welcome_guide_pending`),
    `lang` = VALUES(`lang`),
    `deleted_at` = VALUES(`deleted_at`),
    `deleted_by` = VALUES(`deleted_by`),
    `updated_at` = CURRENT_TIMESTAMP,
    `updated_by` = VALUES(`updated_by`);

-- -----------------------------------------------------------------------------
-- 2. 多语种后缀表（en / th）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sp_tenant_en LIKE sp_tenant;
CREATE TABLE IF NOT EXISTS sp_tenant_th LIKE sp_tenant;

CREATE TABLE IF NOT EXISTS sp_company_en LIKE sp_company;
CREATE TABLE IF NOT EXISTS sp_company_th LIKE sp_company;

CREATE TABLE IF NOT EXISTS sp_department_en LIKE sp_department;
CREATE TABLE IF NOT EXISTS sp_department_th LIKE sp_department;

CREATE TABLE IF NOT EXISTS sp_position_en LIKE sp_position;
CREATE TABLE IF NOT EXISTS sp_position_th LIKE sp_position;

CREATE TABLE IF NOT EXISTS sp_sop_info_en LIKE sp_sop_info;
CREATE TABLE IF NOT EXISTS sp_sop_info_th LIKE sp_sop_info;

CREATE TABLE IF NOT EXISTS sp_sop_version_en LIKE sp_sop_version;
CREATE TABLE IF NOT EXISTS sp_sop_version_th LIKE sp_sop_version;

CREATE TABLE IF NOT EXISTS sp_exam_record_en LIKE sp_exam_record;
CREATE TABLE IF NOT EXISTS sp_exam_record_th LIKE sp_exam_record;

CREATE TABLE IF NOT EXISTS sp_user_session_en LIKE sp_user_session;
CREATE TABLE IF NOT EXISTS sp_user_session_th LIKE sp_user_session;

CREATE TABLE IF NOT EXISTS sp_course_en LIKE sp_course;
CREATE TABLE IF NOT EXISTS sp_course_th LIKE sp_course;

CREATE TABLE IF NOT EXISTS sp_video_en LIKE sp_video;
CREATE TABLE IF NOT EXISTS sp_video_th LIKE sp_video;

CREATE TABLE IF NOT EXISTS sp_material_en LIKE sp_material;
CREATE TABLE IF NOT EXISTS sp_material_th LIKE sp_material;

CREATE TABLE IF NOT EXISTS sp_learning_record_en LIKE sp_learning_record;
CREATE TABLE IF NOT EXISTS sp_learning_record_th LIKE sp_learning_record;

CREATE TABLE IF NOT EXISTS sp_course_progress_en LIKE sp_course_progress;
CREATE TABLE IF NOT EXISTS sp_course_progress_th LIKE sp_course_progress;

CREATE TABLE IF NOT EXISTS sp_user_learning_summary_en LIKE sp_user_learning_summary;
CREATE TABLE IF NOT EXISTS sp_user_learning_summary_th LIKE sp_user_learning_summary;

-- -----------------------------------------------------------------------------
-- 3. dashboard 聚合表加 lang 字段
-- -----------------------------------------------------------------------------
ALTER TABLE sp_sop_leaderboard
    ADD COLUMN lang VARCHAR(8) NOT NULL DEFAULT 'zh'
        COMMENT '业务语种（zh/en/th）'
        AFTER tenant_id;

CREATE INDEX idx_sop_leaderboard_lang_sop_tenant
    ON sp_sop_leaderboard (lang, sop_id, tenant_id, `rank`);

CREATE INDEX idx_sop_leaderboard_lang_user
    ON sp_sop_leaderboard (lang, user_id, tenant_id);

ALTER TABLE sp_dashboard_statistics
    ADD COLUMN lang VARCHAR(8) NOT NULL DEFAULT 'zh'
        COMMENT '业务语种（zh/en/th）'
        AFTER tenant_id;

CREATE INDEX idx_dashboard_statistics_lang_period
    ON sp_dashboard_statistics (tenant_id, lang, period_type, period_start, period_end);

ALTER TABLE sp_user_activity
    ADD COLUMN lang VARCHAR(8) NOT NULL DEFAULT 'zh'
        COMMENT '业务语种（zh/en/th）'
        AFTER tenant_id;

ALTER TABLE sp_user_activity DROP INDEX _tenant_date_uc;

ALTER TABLE sp_user_activity
    ADD CONSTRAINT _tenant_lang_date_uc UNIQUE (tenant_id, lang, stat_date);

CREATE INDEX idx_user_activity_lang_date
    ON sp_user_activity (tenant_id, lang, stat_date);

-- -----------------------------------------------------------------------------
-- 4. 数据迁移
-- -----------------------------------------------------------------------------
UPDATE sp_course
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);

UPDATE sp_course_en
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);

UPDATE sp_course_th
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);

UPDATE sp_material
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);

UPDATE sp_material_en
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);

UPDATE sp_material_th
SET category = CASE
    WHEN category IN ('安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย') THEN 'safety_training'
    WHEN category IN ('技能提升', 'Skill Development', 'การพัฒนาทักษะ') THEN 'skill_upgrade'
    WHEN category IN ('入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่') THEN 'onboarding'
    WHEN category IN ('产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์') THEN 'product_training'
    ELSE category
END
WHERE category IN (
    '安全培训', 'Safety Training', 'การฝึกอบรมด้านความปลอดภัย',
    '技能提升', 'Skill Development', 'การพัฒนาทักษะ',
    '入职培训', 'Onboarding Training', 'การฝึกอบรมพนักงานใหม่',
    '产品培训', 'Product Training', 'การฝึกอบรมผลิตภัณฑ์'
);
