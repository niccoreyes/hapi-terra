@echo off
set default=
if defined default (
  set /p value=Enter value [%default%]:
) else (
  set /p value=Enter value:
)

echo You entered %value%
