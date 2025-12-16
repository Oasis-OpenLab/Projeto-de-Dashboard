DROP DATABASE IF EXISTS Oasis;

CREATE DATABASE Oasis;

USE Oasis;


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
    situacao                VARCHAR(255)
);

