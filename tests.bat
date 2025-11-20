@echo off

uv sync --group test || exit /b
if [%1] == [] (
    rem Run all
    set lint=lint
    set unit=unit
) else (
    set lint=%1
    set unit=%1
)

if [%lint%] == [lint] (
    echo ==== Pylint ====
    uv run pylint --recursive=y --errors-only --jobs=0 E:\Programmering\Python\Moss_Mod
)

if [%1] == [] echo.

if [%unit%] == [unit] (
    echo ==== Unit Tests ====
    uv run python -m unittest tests/test_thoughts.py tests/test_relation_events.py tests/test_group_interaction.py tests/test_conditions.py tests/test_utility.py tests/test_cat.py tests/test_save.py tests/test_filter_patrol.py tests/test_lang.py tests/test_events.py
)
