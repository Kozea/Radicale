-- This is the database schema for PostgreSQL.

create table collection (
       path varchar primary key not null,
       parent_path varchar not null);

create table item (
       name varchar primary key not null,
       tag varchar not null,
       collection_path varchar references collection (path) not null);

create table header (
       key varchar not null,
       value varchar not null,
       collection_path varchar references collection (path) not null,
       primary key (key, collection_path));

create table line (
       key varchar not null,
       value varchar not null,
       item_name varchar references item (name) not null,
       timestamp timestamp not null);

create table property (
       key varchar not null,
       value varchar not null,
       collection_path varchar references collection (path) not null,
       primary key (key, collection_path));
