-- This is the database schema for PostgreSQL and MySQL and SQLite.

create table collection (
       path varchar(200) not null,
       parent_path varchar(200) references collection (path),
       primary key (path));

create table item (
       name varchar(200) not null,
       tag text not null,
       collection_path varchar(200) references collection (path),
       primary key (name));

create table header (
       name varchar(200) not null,
       value text not null,
       collection_path varchar(200) references collection (path),
       primary key (name, collection_path));

create table line (
       name text not null,
       value text not null,
       item_name varchar(200) references item (name),
       timestamp bigint not null,
       primary key (timestamp));

create table property (
       name varchar(200) not null,
       value text not null,
       collection_path varchar(200) references collection (path),
       primary key (name, collection_path));
