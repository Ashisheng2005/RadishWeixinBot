-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS datatest DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE datatest;

-- 创建表 datanumber
DROP TABLE IF EXISTS datanumber;
CREATE TABLE datanumber (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) DEFAULT NULL,
    year INT DEFAULT NULL,
    number INT DEFAULT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入1万行随机数据
DELIMITER $$
DROP PROCEDURE IF EXISTS insert_test_data$$
CREATE PROCEDURE insert_test_data()
BEGIN
    DECLARE i INT DEFAULT 1;
    WHILE i <= 10000 DO
        INSERT INTO datanumber (name, year, number)
        VALUES (
            CONCAT('user_', i),
            FLOOR(RAND() * 50) + 1970,
            FLOOR(RAND() * 10000) + 1
        );
        SET i = i + 1;
    END WHILE;
END$$
DELIMITER ;

CALL insert_test_data();
DROP PROCEDURE IF EXISTS insert_test_data;

-- 验证数据量
SELECT COUNT(*) AS total_rows FROM datanumber;