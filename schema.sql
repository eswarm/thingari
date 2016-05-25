drop table if exists pelican_theme_table;
drop table if exists user_table;

create table pelican_theme_table (
  id integer primary key autoincrement,
  theme text NOT NULL,
  url text NOT NULL
);

create table user_table (
    id integer primary key autoincrement,
    user_name text UNIQUE NOT NULL,
    site_generator text NOT NULL,
    theme text NOT NULL,
    git_repo text,
    git_username text,
    git_password text,
    use_git boolean NOT NULL
);
