# World Cup QA Dataset

本文件夹包含 2026 年世界杯中文新闻正文材料，以及基于这些材料生成的 QA 数据。

## 新闻正文文件

- `01_world_cup_opens_new_48_team_era.txt`
- `02_spain_win_final_against_argentina.txt`
- `03_awards_after_world_cup_final.txt`
- `04_spain_control_and_tactical_title.txt`
- `05_messi_mbappe_and_new_generation.txt`
- `06_fans_ticketing_and_host_city_experience.txt`
- `07_argentina_disciplinary_case_after_final.txt`
- `08_fifa_commercial_plan_draws_backlash.txt`
- `09_england_take_third_after_ten_goal_bronze_match.txt`
- `10_hosts_mexico_canada_usa_under_spotlight.txt`
- `11_knockout_round_tests_new_format.txt`
- `12_non_traditional_teams_gain_world_cup_visibility.txt`
- `13_var_discipline_and_refereeing_under_review.txt`
- `14_what_2026_world_cup_means_for_future.txt`
- `15_spain_second_star_marks_new_cycle.txt`
- `16_argentina_near_repeat_ends_in_bitter_final.txt`
- `17_golden_boot_race_highlights_attacking_firepower.txt`
- `18_fan_festival_becomes_second_stage.txt`
- `19_world_cup_business_and_broadcast_value_soars.txt`
- `20_young_players_take_center_stage_in_2026.txt`
- `21_unai_simon_record_clean_sheets.txt`
- `22_rodri_midfield_master_controls_world_cup.txt`
- `23_final_day_in_new_york_new_jersey.txt`
- `24_reading_world_cup_after_the_final.txt`
- `25_world_cup_2026_attendance_and_goals_record.txt`
- `26_final_tournament_standings_show_global_shift.txt`

## QA 文件

- `qa.json`：根据本文件夹内新闻正文材料生成的 QA 对。

`qa.json` 的每条数据包含 `id`、`question`、`answer` 三个字段。

## 来源说明

材料依据公开来源核对事实后，以中文新闻正文形式重写生成；未整篇复制外部新闻稿。主要参考 FIFA 官方赛事与奖项页面、美联社关于阿根廷纪律指控的报道，以及 Axios 关于国际足联商业计划的报道。
