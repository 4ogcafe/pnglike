-- MySQL Database Schema for RemBG Studio & Admin Backend System
CREATE DATABASE IF NOT EXISTS rembg_studio
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE rembg_studio;

-- 1. Table: removal_jobs
-- Stores history, parameters, dimensions, and performance telemetry for every background removal
CREATE TABLE IF NOT EXISTS removal_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_uuid VARCHAR(36) NOT NULL UNIQUE,
    original_filename VARCHAR(255) NOT NULL,
    output_filename VARCHAR(255) NOT NULL,
    output_url VARCHAR(512) NOT NULL,
    model_used VARCHAR(64) NOT NULL DEFAULT 'u2net',
    alpha_matting BOOLEAN NOT NULL DEFAULT FALSE,
    af_threshold INT NOT NULL DEFAULT 240,
    ab_threshold INT NOT NULL DEFAULT 10,
    ae_size INT NOT NULL DEFAULT 10,
    only_mask BOOLEAN NOT NULL DEFAULT FALSE,
    post_process_mask BOOLEAN NOT NULL DEFAULT FALSE,
    bg_color VARCHAR(32) NULL,
    output_format VARCHAR(16) NOT NULL DEFAULT 'png',
    original_width INT NOT NULL DEFAULT 0,
    original_height INT NOT NULL DEFAULT 0,
    output_size_bytes INT NOT NULL DEFAULT 0,
    process_time_ms FLOAT NOT NULL DEFAULT 0.0,
    batch_id VARCHAR(36) NULL,
    user_id INT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at),
    INDEX idx_model_used (model_used),
    INDEX idx_batch_id (batch_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Table: preset_configs
-- Stores reusable AI & Background Studio presets managed from Admin or Studio
CREATE TABLE IF NOT EXISTS preset_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    model_used VARCHAR(64) NOT NULL DEFAULT 'u2net',
    alpha_matting BOOLEAN NOT NULL DEFAULT FALSE,
    af_threshold INT NOT NULL DEFAULT 240,
    ab_threshold INT NOT NULL DEFAULT 10,
    ae_size INT NOT NULL DEFAULT 10,
    post_process_mask BOOLEAN NOT NULL DEFAULT FALSE,
    bg_mode VARCHAR(32) NOT NULL DEFAULT 'transparent',
    bg_value VARCHAR(255) NULL,
    export_format VARCHAR(16) NOT NULL DEFAULT 'png',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Table: site_settings
-- Dynamic CMS & feature-flag configuration for the public frontend managed via Admin Dashboard
CREATE TABLE IF NOT EXISTS site_settings (
    setting_key VARCHAR(128) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Table: sample_images
-- Manages 1-click sample images displayed on the public frontend
CREATE TABLE IF NOT EXISTS sample_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'Product',
    filename VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Table: admin_users
-- Stores administrator credentials and full profile for the /admin portal
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    full_name VARCHAR(128) NOT NULL DEFAULT 'System Administrator',
    email VARCHAR(128) NOT NULL DEFAULT '',
    avatar_url VARCHAR(512) NULL DEFAULT '',
    avatar_color VARCHAR(32) NOT NULL DEFAULT '#4f46e5',
    phone VARCHAR(32) NOT NULL DEFAULT '',
    designation VARCHAR(128) NOT NULL DEFAULT 'Lead AI Systems Architect',
    department VARCHAR(128) NOT NULL DEFAULT 'DevOps & AI Infrastructure',
    location VARCHAR(128) NOT NULL DEFAULT 'Tokyo, Japan',
    bio TEXT NULL,
    timezone_pref VARCHAR(64) NOT NULL DEFAULT 'Asia/Tokyo (UTC+9)',
    email_notifications BOOLEAN NOT NULL DEFAULT TRUE,
    security_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'superadmin',
    last_login DATETIME NULL,
    updated_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Table: blog_posts
-- Stores blog articles, tutorials, release notes, and SEO metadata managed via Admin Dashboard
CREATE TABLE IF NOT EXISTS blog_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    excerpt TEXT NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'AI Tutorials',
    tags VARCHAR(255) NOT NULL DEFAULT '',
    cover_image VARCHAR(512) NULL,
    author VARCHAR(128) NOT NULL DEFAULT 'Div Sri',
    read_time_minutes INT NOT NULL DEFAULT 4,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    views_count INT NOT NULL DEFAULT 0,
    meta_title VARCHAR(255) NULL,
    meta_description VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_blog_slug (slug),
    INDEX idx_blog_published (is_published),
    INDEX idx_blog_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Table: users
-- Stores registered user accounts, API keys, and plan tiers for the User Dashboard (/dashboard)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(128) NOT NULL UNIQUE,
    full_name VARCHAR(128) NOT NULL DEFAULT '',
    password_hash VARCHAR(255) NOT NULL,
    avatar_color VARCHAR(32) NOT NULL DEFAULT '#3b82f6',
    plan_tier VARCHAR(32) NOT NULL DEFAULT 'Pro Studio',
    api_key VARCHAR(64) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    jobs_count INT NOT NULL DEFAULT 0,
    last_login DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_api_key (api_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
