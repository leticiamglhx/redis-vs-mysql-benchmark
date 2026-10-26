CREATE DATABASE IF NOT EXISTS taxigov CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
USE taxigov;

CREATE TABLE IF NOT EXISTS corrida (
    id VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
    data DATETIME(6) NOT NULL,
    origem VARCHAR(512) NOT NULL,
    destino VARCHAR(512) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    distancia DECIMAL(13,3) NOT NULL,
    bairro_origem VARCHAR(512) NOT NULL DEFAULT '',
    bairro_destino VARCHAR(512) NOT NULL DEFAULT '',
    INDEX idx_corrida_bairro (bairro_origem(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
