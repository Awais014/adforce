create table if not exists campaigns(id serial primary key,user_id text not null,name text,product text,platform text,status text default 'draft',created_at timestamptz default now());
create table if not exists variants(id serial primary key,campaign_id int references campaigns(id) on delete cascade,label text,headline text,body text,cta text,impressions int default 0,clicks int default 0,conversions int default 0,unique(campaign_id,label));
create table if not exists user_memory(user_id text,key text,value text,primary key(user_id,key));
create table if not exists chat_log(id serial primary key,user_id text,thread_id text,user_msg text,reply text,tin int,tout int,ts timestamptz default now());
create index if not exists camp_user on campaigns(user_id);
