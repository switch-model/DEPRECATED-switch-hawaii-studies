drop table if exists tdates;
create table tdates AS
select date(date_time) as date_hi
from system_load group by 1
having count(*) = 24;

drop table if exists tdatelist1;
CREATE TABLE tdatelist1 AS
(select row_number() OVER(),date_hi, extract(year from date_hi), extract(month from date_hi)::int as month_of_year, random() as ord from tdates GROUP BY 2,3,4,5 order by 3,4,5);

drop table if exists tdaysofyear;
CREATE TABLE tdaysofyear AS
SELECT row_number() OVER() AS rownumber,extract(day from dd) AS date_of_year
FROM generate_series('2007-01-01'::timestamp,'2008-12-31'::timestamp, '1 day') as dd;

drop table if exists tdatelist2;
CREATE TABLE tdatelist2 AS
(select B.date_hi,B.month_of_year, B.ord, a.date_of_year::int AS rank 
from tdaysofyear A, tdatelist1 B
WHERE B.row_number = A.rownumber);

drop table if exists tgroups;
create table tgroups as 
select date_hi, month_of_year, rank, 
mod(month_of_year-1,2)+1 as mgroup, 
CASE 
WHEN rank <= 28 THEN mod(rank-1, 7)+1 
ELSE NULL
END AS rgroup
from tdatelist2;

drop table if exists hours;
CREATE TABLE hours AS
SELECT date_time, row_number() OVER() AS hournum FROM system_load;

drop table if exists tperiods;
create table tperiods as
select hournum as periodnum from hours where hournum between 1 and 4;


drop table if exists tmonths;
create table tmonths (month_of_year smallint, days_in_month double precision);
insert into tmonths values 
  (1, 31), (2, 28), (3, 31), (4, 30), (5, 31), (6, 30),
  (7, 31), (8, 31), (9, 30), (10, 31), (11, 30), (12, 31);

drop table if exists tselect;
create table tselect as
select d.mgroup, d.rgroup,
  mod(extract(hour from h.date_time)::int,2) as hgroup, c.technology, 
  avg(c.cap_factor) as avg_cap_factor, 
  count(distinct c.date_time) as n_samples 
  from cap_factor c join hours h on h.date_time=c.date_time 
    join tgroups d on d.date_hi = date(h.date_time)
  group by 1, 2, 3, 4;

drop table if exists tdatelist2_copy;
CREATE TABLE tdatelist2_copy AS
SELECT * FROM tdatelist2;

-- From this, we find out that the odd months in rgroup 4 have the lowest RMSE.
-- # even numbered months, rank group 4, seems to have a reasonable average capacity factor and 
-- distribution of weekdays vs weekends and minimum rmse

delete from tdatelist2 where rank > 28 or mod(rank-1, 7)+1 <> 4; 

-- select a.mgroup, a.rgroup, a.hgroup,
-- SQRT(AVG(POWER(b.cap_factor - a.avg_cap_factor, 2))) as RMSE
-- from tselect a, (select technology, avg(cap_factor) as cap_factor from cap_factor
-- group by 1) as b
-- where a.technology = b.technology
-- group by 1,2,3
-- order by 4;

drop table if exists tdatelist_next;
create table tdatelist_next as
select distinct on(rank,month_of_year) date_hi, month_of_year,ord,rank
from
(select date_hi,month_of_year,rank,ord from tdatelist2
group by 1,2,3,4
order by month_of_year,ord) dd
order by rank, month_of_year,ord;

-- For re-ranking again

UPDATE tdatelist_next set rank = case
WHEN rank = 4 then 1
WHEN rank = 11 then 2
WHEN rank = 18 then 3
WHEN rank = 25 then 4
END;


\set start_year 2015
\set years_per_period 3

drop table if exists tstudy_dates_avg_temp1;
create table tstudy_dates_avg_temp1 as
select (p.periodnum-1) * :years_per_period + :start_year as period, l.date_hi, l.month_of_year, 
(m.days_in_month-1)* (:years_per_period) as hours_in_sample
from tperiods p,tmonths m, tdatelist_next l
where (l.rank=p.periodnum and l.month_of_year=m.month_of_year)
order by 1,3,2;

drop table if exists tmaxdate;
create table tmaxdate as
select distinct on (extract(month from date_time)) date_time, 
extract(month from date_time) as month_of_year, system_load 
from system_load
order by extract(month from date_time), system_load desc;

drop table if exists tmaxdate_match;
create table tmaxdate_match as
select a.date_time::date as date_hi, 
a.month_of_year,(row_number() OVER (ORDER BY a.month_of_year) - 1) % 4 + 1  as rank
from tmaxdate a, tstudy_dates_avg_temp1 b
where extract(month from a.date_time) = extract(month from b.date_hi)
order by 2;

\set start_year 2015
\set years_per_period 3

insert into tstudy_dates_avg_temp1 (period, date_hi, month_of_year, hours_in_sample)
select (p.periodnum-1) * :years_per_period + :start_year as period, 
a.date_hi, a.month_of_year,
:years_per_period as hours_in_sample
from tmaxdate_match a, tperiods p
where a.rank=p.periodnum
order by 1,3,2;

drop table if exists study_date_new;
CREATE TABLE study_date_new AS
SELECT period, (mod(period, 100)) * 10000000 + mod(extract(year from date_hi)::int, 100) * 100000 + 
 extract(month from date_hi)*1000 + extract(day from date_hi)*10 + 
 (case 
 when hours_in_sample < 80 then 1
 else 0
 end) as study_date,
month_of_year, date_hi as date, hours_in_sample
FROM tstudy_dates_avg_temp1;

ALTER TABLE study_date_new ADD PRIMARY KEY (study_date);

drop table if exists date_time;
CREATE TABLE date_time AS
SELECT DISTINCT date_time::date as date, date_time,
EXTRACT(HOUR from date_time)::int as hour_of_day
FROM system_load
ORDER by date_time;

drop table if exists study_hour_new;
CREATE TABLE study_hour_new AS
SELECT s.study_date, 
(((mod(s.period, 100)) * 10000 + s.month_of_year * 100 + d.hour_of_day) * 10000 + 
(mod(extract(year from s.date)::int, 10) * 1000 + extract(day from s.date)*10) +
 (case 
 when s.hours_in_sample < 80 then 1
 else 0
 end)) as study_hour,
d.hour_of_day, d.date_time
FROM study_date_new s, date_time d 
WHERE d.date = s.date
order by 1,2;

ALTER TABLE study_hour_new ADD PRIMARY KEY (study_date, study_hour, date_time);

-- The following code was added by Matthias Fripp 2015-06-18.
-- Most of it should be moved into the earlier workflow.


-- Rename the existing study_date and study_hour tables (they can be removed eventually) [Have been removed].
-- Then allow study_date and study_hour to hold multiple different time samples,
-- identified by a new "time_sample" column.
-- Then copy the pre-existing "_new" samples into these tables, labeling them "main".
-- Then make a sample called "2007" by shifting the 2015 and 2018 periods from "main"
-- to 2007 and 2008, and omitting the rest.

-- alter table study_date rename to study_date_first;
drop table if exists study_date_main;
alter table study_date_new rename to study_date_main;

drop table if exists study_hour_main;
-- alter table study_hour rename to study_hour_first;
alter table study_hour_new rename to study_hour_main;

drop table if exists study_date;
create table study_date (like study_date_main);
drop table if exists study_hour;
create table study_hour (like study_hour_main);
alter table study_date add column time_sample varchar(20);
alter table study_hour add column time_sample varchar(20);

alter table study_date add primary key (time_sample, study_date);
--drop index if exists sdh;
create index sdh on study_hour (time_sample, study_date, study_hour);

insert into study_date select *, 'main' as time_sample from study_date_main;
insert into study_hour select *, 'main' as time_sample from study_hour_main;

insert into study_date select *, '2007' as time_sample 
    from study_date_main where period in (2015, 2018);
update study_date set 
        period = case when period = 2015 then 2007 when period = 2018 then 2008 else period end,
        hours_in_sample = hours_in_sample / 3.0
    where time_sample = '2007';

insert into study_hour select study_hour_main.*, '2007' as time_sample 
    from study_hour_main join study_date using (study_date)
    where time_sample = '2007';

-- Make a study_periods table, showing the periods included in each time_sample.
DROP TABLE IF EXISTS study_periods;
CREATE TABLE study_periods AS 
    SELECT DISTINCT time_sample, period 
        FROM study_date 
        ORDER BY 1, 2;
alter table study_periods add primary key (time_sample, period);

-- create some extra columns to support the pyomo version of switch,
-- which needs more data on each time series (a.k.a. study_date)
-- (see timescales.py)
-- In the future, these weights should be created in the main workflow above! 
-- (and hours_in_sample can be omitted or calculated from them)
alter table study_date 
    add column ts_num_tps int,                     -- number of timepoints in a timeseries
    add column ts_duration_of_tp double precision, -- duration in hours of each timepoint within a series
    add column ts_scale_to_period double precision; -- (length of period) = scale_to_period * num_tps * duration_of_tp

update study_date set
    ts_num_tps = (select count(*) from study_hour) / (select count(*) from study_date);
update study_date set
    ts_duration_of_tp = 24.0 / ts_num_tps;
update study_date set
    ts_scale_to_period = hours_in_sample / ts_duration_of_tp;

-- make short four-day period for testing
insert into study_periods (time_sample, period) 
    select 'four_day' as time_sample, period 
    from study_periods where time_sample='2007';

insert into study_date (period, study_date, month_of_year, date, hours_in_sample, time_sample, ts_num_tps, ts_duration_of_tp, ts_scale_to_period)
    select period, study_date, month_of_year, date, hours_in_sample, 'four_day' as time_sample, ts_num_tps, ts_duration_of_tp, 365.0/2 as ts_scale_to_period
    from study_date where time_sample='2007' and month_of_year in (1, 7) and ts_scale_to_period > 1;

insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
    select h.study_date, study_hour, hour_of_day, date_time, 'four_day' as time_sample
        from study_hour h join study_date d using (study_date)
        where d.time_sample='four_day' and h.time_sample='2007';
        
update study_hour h
    set study_date = d.period*10 + extract(month from d.date) 
    from study_date d
    where h.time_sample='four_day' and d.time_sample='four_day' and d.date=date_trunc('day', h.date_time);
update study_date set study_date = period*10 + extract(month from date) where time_sample='four_day';
update study_hour set study_hour = study_date * 100 + hour_of_day where time_sample='four_day';

-- switch the columns to int datatypes so they don't get exported to switch with ".0" at the end
alter table study_date 
    alter column study_date type bigint;
alter table study_hour 
    alter column study_hour type bigint,
    alter column study_date type bigint;

-- Short forward-looking study period
insert into study_periods (time_sample, period) values ('2016test', 2016), ('2016test', 2020);
insert into study_date (time_sample, period, study_date, date)
    values
        ('2016test', 2016, 1601, date '2007-01-15'),
        ('2016test', 2016, 1607, date '2007-07-15'),
        ('2016test', 2020, 2001, date '2008-01-15'),
        ('2016test', 2020, 2007, date '2008-07-15');
update study_date set 
    ts_num_tps = 24,
    ts_duration_of_tp = 1,
    ts_scale_to_period = 365.25*4/2
    where time_sample='2016test';
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
    select study_date, 100*study_date + extract(hour from date_time) as study_hour,
        extract(hour from date_time) as hour_of_day, date_time, time_sample
    from study_date d join system_load l 
        on d.date=date_trunc('day', l.date_time) and l.load_zone='Oahu'
    where time_sample='2016test'
    order by 1, 2;
    
-- Small but long-term study
insert into study_periods (time_sample, period) values ('rps_test', 2015), ('rps_test', 2020), ('rps_test', 2025), ('rps_test', 2030);
insert into study_date (time_sample, period, study_date, date)
    values
        ('rps_test', 2015, 1501, date '2007-01-15'),
        ('rps_test', 2015, 1507, date '2007-07-15'),
        ('rps_test', 2020, 2001, date '2008-01-15'),
        ('rps_test', 2020, 2007, date '2008-07-15'),
        ('rps_test', 2025, 2501, date '2007-02-15'),
        ('rps_test', 2025, 2507, date '2007-08-15'),
        ('rps_test', 2030, 3001, date '2008-02-15'),
        ('rps_test', 2030, 3007, date '2008-08-15');
update study_date set 
    ts_num_tps = 24,
    ts_duration_of_tp = 1,
    ts_scale_to_period = 365.25*5/2
    where time_sample='rps_test';
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
    select study_date, 100*study_date + extract(hour from date_time) as study_hour,
        extract(hour from date_time) as hour_of_day, date_time, time_sample
    from study_date d join system_load l 
        on d.date=date_trunc('day', l.date_time) and l.load_zone='Oahu'
    where time_sample='rps_test'
    order by 1, 2;

-- Small but long-term study
delete from study_periods where time_sample='rps_test_45';
delete from study_date where time_sample='rps_test_45';
delete from study_hour where time_sample='rps_test_45';
insert into study_periods (time_sample, period) values ('rps_test_45', 2021), ('rps_test_45', 2029), ('rps_test_45', 2037), ('rps_test_45', 2045);
insert into study_date (time_sample, period, study_date, date)
    values
        ('rps_test_45', 2021, 2101, date '2007-01-15'),
        ('rps_test_45', 2021, 2107, date '2007-07-15'),
        ('rps_test_45', 2029, 2901, date '2008-01-15'),
        ('rps_test_45', 2029, 2907, date '2008-07-15'),
        ('rps_test_45', 2037, 3701, date '2007-02-15'),
        ('rps_test_45', 2037, 3707, date '2007-08-15'),
        ('rps_test_45', 2045, 4501, date '2008-02-15'),
        ('rps_test_45', 2045, 4507, date '2008-08-15');
update study_date set 
    ts_num_tps = 24,
    ts_duration_of_tp = 1,
    ts_scale_to_period = 365.25*8/2
    where time_sample='rps_test_45';
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
    select study_date, 100*study_date + extract(hour from date_time) as study_hour,
        extract(hour from date_time) as hour_of_day, date_time, time_sample
    from study_date d join system_load l 
        on d.date=date_trunc('day', l.date_time) and l.load_zone='Oahu'
    where time_sample='rps_test_45'
    order by 1, 2;

-- Create an RPS study based on the "main" time samples, but shifted into the future

delete from study_date where time_sample='rps';
insert into study_date (period,  study_date, month_of_year, date, hours_in_sample, time_sample, ts_num_tps, ts_duration_of_tp, ts_scale_to_period)
  select 2021 + 8 * cast((period-2015)/3.0 as int) as period, 
    study_date,
    month_of_year, date, 8.0*hours_in_sample/3.0 as hours_in_sample, 
    'rps' as time_sample, ts_num_tps, 
    ts_duration_of_tp, 8.0*ts_scale_to_period/3.0 as ts_scale_to_period
  from study_date where time_sample = 'main';
-- note: this comes after, so it can use the new value of period.
-- also note: it has to be run twice because it can create duplicate keys otherwise
update study_date 
    set study_date=(-1)*(mod(period, 100)*1e7+mod(study_date,1e7))
    where time_sample = 'rps';
update study_date 
    set study_date=(-1)*study_date 
    where time_sample = 'rps' and study_date < 0;

delete from study_hour where time_sample='rps';
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
  select study_date, study_hour, hour_of_day, date_time, 
    'rps' as time_sample
  from study_hour where time_sample = 'main'
  order by 1, 2;
update study_hour 
  set study_date = (21+(trunc(study_date/1e7)-15)*8.0/3.0)*1e7+mod(study_date,1e7),
    study_hour = (21+(trunc(study_hour/1e8)-15)*8.0/3.0)*1e8+mod(study_hour,1e8)
  where time_sample = 'rps';

delete from study_periods where time_sample='rps';
insert into study_periods
    select distinct time_sample, period from study_date
    where time_sample='rps'
    order by 2;


-- mini RPS study (even months, even hours) for reasonable results in relatively short time

drop table if exists tdoublemonths;
create table tdoublemonths
    (month_of_year smallint primary key, days_in_month smallint);
insert into tdoublemonths values 
  (1, 59), (2, 59), (3, 61), (4, 61), (5, 61), (6, 61),
  (7, 62), (8, 62), (9, 61), (10, 61), (11, 61), (12, 61);
\set start_year 2021
\set years_per_period 8

delete from study_date where time_sample='rps_mini';
insert into study_date 
    (period, study_date, month_of_year, date, 
    hours_in_sample, time_sample, ts_num_tps, ts_duration_of_tp, ts_scale_to_period)
    select period, study_date, d.month_of_year, date,
        0.0 as hours_in_sample, 
        'rps_mini' as time_sample,
        12 as ts_num_tps, 2.0 as ts_duration_of_tp,
        case when ts_scale_to_period < 100 then 2*:years_per_period 
            else (days_in_month-2)*:years_per_period end as ts_scale_to_period
    from study_date d join tdoublemonths m using (month_of_year)
    where time_sample = 'rps' and mod(month_of_year, 2)=0
    order by 1, 3, 5 desc, 4;

delete from study_hour where time_sample='rps_mini';
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
  select h.study_date, study_hour, hour_of_day, date_time, 
    'rps_mini' as time_sample
  from study_hour h join study_date d on (d.time_sample='rps_mini' and d.study_date=h.study_date)
  where h.time_sample = 'rps' and mod(hour_of_day, 2)=0 
  order by period, month_of_year, hours_in_sample desc, hour_of_day;

delete from study_periods where time_sample='rps_mini';
insert into study_periods
    select distinct time_sample, period from study_date
    where time_sample='rps_mini'
    order by 2;



-- tiny study for testing iterative approaches
delete from study_date where time_sample='tiny';
insert into study_date (time_sample, period, study_date, date)
    values
        ('tiny', 2021, 2107, date '2007-07-15'),
        ('tiny', 2037, 3707, date '2007-07-15');
update study_date set 
    ts_num_tps = 8,
    ts_duration_of_tp = 3,
    ts_scale_to_period = 365.25*16
    where time_sample='tiny';
delete from study_periods where time_sample='tiny';
insert into study_periods (time_sample, period) 
    select distinct time_sample, period from study_date where time_sample = 'tiny' order by 1, 2;
insert into study_hour (study_date, study_hour, hour_of_day, date_time, time_sample)
    select study_date, 100*study_date + extract(hour from date_time) as study_hour,
        extract(hour from date_time) as hour_of_day, date_time, time_sample
    from study_date d join system_load l 
        on d.date=date_trunc('day', l.date_time) and l.load_zone='Oahu'
    where time_sample='tiny' and cast(extract(hour from date_time) as int) % 3 = 0
    order by 1, 2;


-- select *, '2007' as time_sample 
--    from study_date_main where period in (2015, 2018);
    
update study_date set 
        period = case when period = 2015 then 2007 when period = 2018 then 2008 else period end,
        hours_in_sample = hours_in_sample / 3.0
    where time_sample = '2007';

insert into study_hour select study_hour_main.*, '2007' as time_sample 
    from study_hour_main join study_date using (study_date)
    where time_sample = '2007';