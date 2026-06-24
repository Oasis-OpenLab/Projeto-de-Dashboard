/*
=====================================================================
SCRIPT DE INICIALIZAÇÃO DO BANCO DE DADOS - PROJETO OÁSIS
=====================================================================
Responsável por recriar a estrutura de armazenamento local do sistema.
Sempre que uma nova busca principal é feita, este script é executado 
para limpar os dados antigos e preparar a tabela para os novos resultados, 
garantindo que o Dashboard sempre exiba o lote mais recente.
*/

DROP DATABASE IF EXISTS Oasis;

CREATE DATABASE Oasis;

USE Oasis;

-- Tabela principal que armazena os metadados dos projetos e os scores da IA
CREATE TABLE Projetos
(
    id                      INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    norma                   VARCHAR(255) NOT NULL,
    descricao               VARCHAR(255) NOT NULL,
    datadeapresentacao      DATE,
    autor                   TEXT,
    partido                 VARCHAR(50),
    ementa                  TEXT,
    linkpdf                 VARCHAR(255),
    linkweb                 VARCHAR(255),
    indexacao               TEXT,
    ultimoestado            VARCHAR(255),
    dataultimo              DATE,
    situacao                VARCHAR(255),
    -- Scores gerados pela Inteligência Artificial (Bi-Encoder e Cross-Encoder)
    score_relevancia        DECIMAL(10,4),
    metodo VARCHAR(100)
);