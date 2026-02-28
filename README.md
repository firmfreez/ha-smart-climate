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

В категориях выбираются `climate.*` устройства. Интеграция активирует категории накопительно:
- категория 1 -> только `cat1`
- категория 2 -> `cat1 + cat2`
- категория 3 -> `cat1 + cat2 + cat3`

Также задаются:
- `weather_sensitive_climates` — климатические устройства, которые ограничиваются наружной температурой;
- `shared_climates` — устройства, обслуживающие несколько комнат (участвуют через арбитраж shared demand).

## Настройка (подробно)

1. В Config Flow выбери источник наружной температуры:
   - `weather` или `sensor`,
   - политику при отсутствии наружной температуры.
2. Для каждой комнаты укажи:
   - `room_name`,
   - `temp_sensors`,
   - `heat_category_1/2/3`,
   - `cool_category_1/2/3`,
   - `weather_sensitive_climates`,
   - `shared_climates`,
   - `dumb_devices_json`.
3. В Options Flow настрой:
   - режим (`off/per_room/global`) и тип (`normal/fast/extreme`),
   - global/per-room target и tolerance,
   - пороги включения категорий 2 и 3 для heat/cool,
   - safe outdoor ranges,
   - after_reach поведение,
   - shared arbitration.

### Dumb устройства

Для dumb-устройств обязательно указывать **оба** скрипта: включение и выключение.

Поле `dumb_devices_json` принимает массив:

```json
[
  {
    "on_script": "script.room1_heater_on",
    "off_script": "script.room1_heater_off",
    "device_type": "heat",
    "participation": "until_reach_target",
    "category": 2
  }
]
```

Поля:
- `on_script` — обязательно, `script.*`
- `off_script` — обязательно, `script.*`
- `device_type` — `heat` или `cool`
- `participation` — `off` | `always_on` | `until_reach_target`
- `category` — `1` | `2` | `3` (с какой категории устройство начинает участвовать)

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
