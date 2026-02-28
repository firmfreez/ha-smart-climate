# Умный климат (`smart_climate`)

Кастомная интеграция Home Assistant для управления климатом по комнатам с поддержкой:
- режимов `off`, `per_room`, `global`
- профилей `normal`, `fast`, `extreme`
- категорий устройств 1/2/3 для нагрева и охлаждения
- погодных ограничений для кондиционеров/тепловых насосов
- shared climate устройств с арбитражем (`max_demand`, `priority_room`, `average_request`)
- fallback-сущностей для управления из HA UI

## Установка через HACS

1. В HACS: `Integrations` -> `⋮` -> `Custom repositories`.
2. Добавьте URL репозитория и тип `Integration`.
3. Найдите `Умный климат` и установите.
4. Перезапустите Home Assistant.
5. Перейдите в `Settings` -> `Devices & Services` -> `Add Integration` -> `Smart Climate`.

## Сущности

- `select.smart_climate_mode`
- `select.smart_climate_type`
- `number.smart_climate_global_target`
- `number.smart_climate_global_tolerance`
- `switch.smart_climate_<room>_enabled`
- `number.smart_climate_<room>_target`
- `number.smart_climate_<room>_tolerance`
- `sensor.smart_climate_<room>_current_temp`
- `sensor.smart_climate_<room>_phase`
- `sensor.smart_climate_outdoor_temp`

## Категории устройств

Для каждой комнаты задаются отдельные списки:
- `heat_category_1`, `heat_category_2`, `heat_category_3`
- `cool_category_1`, `cool_category_2`, `cool_category_3`

Можно добавлять `climate.*` и `script.*` устройства. При выборе категории интеграция активирует устройства накопительно (`cat1`, затем `cat1+cat2`, затем `cat1+cat2+cat3`).

Также задаются:
- `weather_sensitive_climates` — климатические устройства, которые ограничиваются наружной температурой;
- `shared_climates` — устройства, обслуживающие несколько комнат (участвуют через арбитраж shared demand).

## Релиз под HACS

1. Подготовьте изменения и закоммитьте.
2. Обновите тег: `git tag vX.Y.Z`.
3. Отправьте тег: `git push origin vX.Y.Z`.
4. Workflow `Release`:
   - подставит `X.Y.Z` в `manifest.json` и `const.py` внутри релизной сборки,
   - соберет zip (`custom_components/smart_climate/**`),
   - создаст GitHub Release и прикрепит asset.
5. HACS увидит новый релиз по тегу и версии из `manifest.json` в zip asset.

## Разработка

```bash
python -m pip install -U pip
pip install -e .[dev]
ruff check .
pytest
```
