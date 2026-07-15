#!/usr/bin/env python3
"""Prepare translation batches, assemble Stellaris YAML, and validate tokens."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "1708335879/localisation/sw_factions_l_english.yml"
MOD = ROOT / "sw_factions_russian"
LOCALE = MOD / "localisation/russian"
WORK = Path("/tmp/sw_factions_russian_translation")
CORE_OUT = LOCALE / "zzz_sw_factions_core_l_russian.yml"

ENTRY_RE = re.compile(r'^\s*([^:#][^:]*):(?:\d+)?\s+"(.*)"\s*$')
TOKEN_RE = re.compile(
    r'\\n|\\"|\$[^$]+\$|§.|£[A-Za-z0-9_]+|\[[^\]]+\]|%[A-Za-z]+%|@[A-Za-z0-9_]+'
)
MARKER_RE = re.compile(r"^@@SW(\d{4})@@\s?(.*)$")


def parse_source() -> list[dict[str, object]]:
    lines = SOURCE.read_text(encoding="utf-8-sig").splitlines()
    items: list[dict[str, object]] = []
    for line_no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ENTRY_RE.match(line)
        if not match:
            raise ValueError(f"Cannot parse source line {line_no}: {line}")
        items.append({"key": match.group(1).strip(), "value": match.group(2), "line": line_no})

    last_index = {item["key"]: index for index, item in enumerate(items)}
    return [item for index, item in enumerate(items) if last_index[item["key"]] == index]


def protect(value: str, item_index: int) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        placeholder = f"ZXQ{item_index:04d}T{len(replacements):02d}QXZ"
        replacements[placeholder] = match.group(0)
        return placeholder

    return TOKEN_RE.sub(replace, value), replacements


def prepare(batch_chars: int) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    batches = WORK / "batches"
    batches.mkdir(exist_ok=True)
    for old in batches.glob("*.txt"):
        old.unlink()
    for old in (WORK / "translated").glob("*.txt") if (WORK / "translated").exists() else []:
        old.unlink()

    manifest: list[dict[str, object]] = []
    batch_lines: list[str] = []
    batch_size = 0
    batch_no = 0

    def flush() -> None:
        nonlocal batch_lines, batch_size, batch_no
        if not batch_lines:
            return
        (batches / f"batch_{batch_no:03d}.txt").write_text("\n".join(batch_lines) + "\n", encoding="utf-8")
        batch_no += 1
        batch_lines = []
        batch_size = 0

    for index, item in enumerate(parse_source()):
        protected, tokens = protect(str(item["value"]), index)
        line = f"@@SW{index:04d}@@ {protected}"
        if batch_lines and batch_size + len(line) + 1 > batch_chars:
            flush()
        batch_lines.append(line)
        batch_size += len(line) + 1
        manifest.append({**item, "index": index, "protected": protected, "tokens": tokens})
    flush()

    (WORK / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(manifest)} effective keys in {batch_no} batches at {WORK}")


def read_translations() -> dict[int, str]:
    translated_dir = WORK / "translated"
    found: dict[int, str] = {}
    for path in sorted(translated_dir.glob("batch_*.txt")):
        current_index: int | None = None
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            marker = MARKER_RE.match(raw_line)
            if marker:
                current_index = int(marker.group(1))
                found[current_index] = marker.group(2)
            elif current_index is not None:
                found[current_index] += " " + raw_line.strip()
    fallback_dir = MOD / "tools/local_fallbacks"
    for path in sorted(fallback_dir.glob("batch_*.txt")):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            marker = MARKER_RE.match(raw_line)
            if not marker:
                raise ValueError(f"Invalid fallback line in {path}: {raw_line}")
            found[int(marker.group(1))] = marker.group(2)
    return found


TEMPLATE_REPLACEMENTS = (
    ("Galactic Republic Fleet", "флот Галактической Республики"),
    ("Republic Fleet", "флот Республики"),
    ("Republic Patriots", "патриоты Республики"),
    ("Republic Militia", "ополчение Республики"),
    ("Confederate Insurgents", "повстанцы Конфедерации"),
    ("First Order Fleet", "флот Первого Ордена"),
    ("First Order Patriots", "патриоты Первого Ордена"),
    ("First Order Insurgents", "повстанцы Первого Ордена"),
    ("Sith-Imperial Fleet", "флот Империи ситхов"),
    ("Undead Alliance Army", "армия нежити Альянса"),
    ("Zakuul Militia", "ополчение Закуула"),
    ("Eternal Fleet Detatchment", "отряд Вечного флота"),
    ("Dark Trooper Phase III Army", "армия тёмных солдат фазы III"),
    ("Dark Trooper Phase II Battalion", "батальон тёмных солдат фазы II"),
    ("Dark Trooper Phase II Army", "армия тёмных солдат фазы II"),
    ("Dark Trooper Phase I Army", "армия тёмных солдат фазы I"),
    ("Project Blackwing", "проект «Чёрное крыло»"),
    ("Dead Man's Legion", "легион мертвецов"),
    ("Knights of Ren", "рыцари Рен"),
    ("Knights of Zakuul", "рыцари Закуула"),
    ("Scions of Zakuul", "наследники Закуула"),
    ("Beasts of Zildrog", "звери Зилдрога"),
    ("Zildrog's Chosen", "избранники Зилдрога"),
    ("Horizon Guard", "Стражи Горизонта"),
    ("Neo-Crusader Armada", "армада неокрестоносцев"),
    ("Neo-Crusader Army", "армия неокрестоносцев"),
    ("Mandalorian Tribes", "мандалорские племена"),
    ("Mandalorian Clans", "мандалорские кланы"),
    ("Mandalorian Raiders", "мандалорские налётчики"),
    ("Massassi Tribes", "племена массасси"),
    ("Kissai Caste", "каста киссаи"),
    ("Sithspawn", "порождения ситхов"),
    ("Sitspawn War Beasts", "боевые звери-порождения ситхов"),
    ("Rakghoul Crusaders", "крестоносцы-ракгулы"),
    ("Mandallian Giants", "мандаллианские гиганты"),
    ("Siege Skytrooper", "осадный скайтрупер"),
    ("Elite Skytrooper Army", "армия элитных скайтруперов"),
    ("Skytrooper War-Droid Garrison", "гарнизон боевых дроидов-скайтруперов"),
    ("Skytrooper Garrison", "гарнизон скайтруперов"),
    ("Skytrooper Army", "армия скайтруперов"),
    ("Terror Trooper Legion", "легион солдат ужаса"),
    ("Death Trooper Legion", "легион солдат смерти"),
    ("Conscript Legion", "легион призывников"),
    ("Dark Honor Guard Division", "дивизия Тёмной почётной гвардии"),
    ("Dark Jedi", "тёмные джедаи"),
    ("One Sith Warriors", "воины Единых ситхов"),
    ("Imperial Shocktrooper Legion", "легион имперских штурмовиков"),
    ("Imperial Royal Army", "королевская имперская армия"),
    ("First Order Droid Occupation Force", "оккупационные силы дроидов Первого Ордена"),
    ("Imperial Droid Occupation Force", "оккупационные силы имперских дроидов"),
    ("Sith War-Droid Occupation Force", "оккупационные силы боевых дроидов ситхов"),
    ("Confederate Droid Occupation Force", "оккупационные силы дроидов Конфедерации"),
    ("Assault Droid Occupation Force", "оккупационные силы штурмовых дроидов"),
    ("War-Droid Occupation Force", "оккупационные силы боевых дроидов"),
    ("First Order Security Droid Garrison", "гарнизон охранных дроидов Первого Ордена"),
    ("Imperial Security Droid Garrison", "гарнизон имперских охранных дроидов"),
    ("Republic Planetary Defense Force", "планетарные силы обороны Республики"),
    ("Imperial Planetary Garrison", "планетарный гарнизон Империи"),
    ("Confederate Planetary Garrison", "планетарный гарнизон Конфедерации"),
    ("First Order Occupation Force", "оккупационные силы Первого Ордена"),
    ("Imperial Occupation Force", "имперские оккупационные силы"),
    ("Republic Occupation Force", "оккупационные силы Республики"),
    ("Confederate Occupation Force", "оккупационные силы Конфедерации"),
    ("Mandalorian Occupation Force", "мандалорские оккупационные силы"),
    ("Massassi Occupation Force", "оккупационные силы массасси"),
    ("Skytrooper Occupation Force", "оккупационные силы небесных солдат"),
    ("First Order Clonetrooper Legion", "легион клонов-солдат Первого Ордена"),
    ("Imperial Clonetrooper Legion", "имперский легион клонов-солдат"),
    ("Imperial Clone Trooper Legion", "имперский легион клонов-солдат"),
    ("Republic Clone Trooper Legion", "республиканский легион клонов-солдат"),
    ("Spaarti Clone Trooper Legion", "легион клонов-солдат Спаарти"),
    ("Veteran Clonetrooper Legion", "легион ветеранов-клонов"),
    ("Clone Trooper Legion", "легион клонов-солдат"),
    ("First Order Droid Garrison", "гарнизон дроидов Первого Ордена"),
    ("First Order Droid Army", "армия дроидов Первого Ордена"),
    ("First Order Dark Trooper Army", "армия тёмных солдат Первого Ордена"),
    ("First Order Garrison", "гарнизон Первого Ордена"),
    ("First Order Army", "армия Первого Ордена"),
    ("First Order", "Первого Ордена"),
    ("Galactic Republic", "Галактической Республики"),
    ("Republic Ground Forces", "наземные силы Республики"),
    ("Republic Special Forces", "спецназ Республики"),
    ("Republic Security Force", "служба безопасности Республики"),
    ("Republic Power Guard Army", "армия Стражи силы Республики"),
    ("Republic Trooper Army", "армия солдат Республики"),
    ("Republic Army Division", "дивизия армии Республики"),
    ("Republic Garrison", "гарнизон Республики"),
    ("Republic Army", "армия Республики"),
    ("Republic", "Республики"),
    ("Alliance Special Forces", "спецназ Альянса"),
    ("Alliance Infantry Division", "пехотная дивизия Альянса"),
    ("Alliance Army Division", "дивизия армии Альянса"),
    ("Alliance Garrison", "гарнизон Альянса"),
    ("Alliance Militia", "ополчение Альянса"),
    ("Alliance", "Альянса"),
    ("Confederate Droid Garrison", "гарнизон дроидов Конфедерации"),
    ("Confederate Droid Army", "армия дроидов Конфедерации"),
    ("Confederate Garrison", "гарнизон Конфедерации"),
    ("Confederate Militia", "ополчение Конфедерации"),
    ("Confederate Army", "армия Конфедерации"),
    ("Confederate", "Конфедерации"),
    ("Sith-Imperial Garrison", "гарнизон Империи ситхов"),
    ("Sith-Imperial Army", "армия Империи ситхов"),
    ("Sith-Imperial", "Империи ситхов"),
    ("Sith Ground Forces", "наземные силы ситхов"),
    ("Sith Occupation Force", "оккупационные силы ситхов"),
    ("Sith Droid Garrison", "гарнизон дроидов ситхов"),
    ("Sith Droid Army", "армия дроидов ситхов"),
    ("Sith War-Droid Garrison", "гарнизон боевых дроидов ситхов"),
    ("Sith War-Droid Army", "армия боевых дроидов ситхов"),
    ("Sith Army", "армия ситхов"),
    ("Sith Armada", "армада ситхов"),
    ("Sith War Fleet", "военный флот ситхов"),
    ("Sith", "ситхов"),
    ("Imperial Battle Droid Garrison", "гарнизон имперских боевых дроидов"),
    ("Imperial Battle Droid Army", "армия имперских боевых дроидов"),
    ("Imperial Droid Garrison", "гарнизон имперских дроидов"),
    ("Imperial Droid Army", "армия имперских дроидов"),
    ("Imperial Army Garrison", "гарнизон имперской армии"),
    ("Imperial Army Division", "дивизия имперской армии"),
    ("Imperial Garrison", "имперский гарнизон"),
    ("Imperial Army", "имперская армия"),
    ("Imperial Knights", "Имперские рыцари"),
    ("Imperial", "имперский"),
    ("Mandalorian Shock Troopers", "мандалорские штурмовики"),
    ("Mandalorian Clone Army", "мандалорская армия клонов"),
    ("Mandalorian Garrison", "мандалорский гарнизон"),
    ("Mandalorian Warriors", "мандалорские воины"),
    ("Mandalorian Knights", "мандалорские рыцари"),
    ("Mandalorian Recruits", "мандалорские рекруты"),
    ("Mandalorian Army", "мандалорская армия"),
    ("Mandalorian", "мандалорский"),
    ("Zakuulan Overwatch Security Force", "служба безопасности Закуула"),
    ("Zakuulan Clone Trooper Legion", "легион клонов-солдат Закуула"),
    ("Zakuulan Exiles", "изгнанники Закуула"),
    ("Zakuul Trooper Assault Division", "штурмовая дивизия солдат Закуула"),
    ("Zakuul Droid Garrison", "гарнизон дроидов Закуула"),
    ("Zakuul Garrison", "гарнизон Закуула"),
    ("Zakuul Knights", "рыцари Закуула"),
    ("Zakuul Walker", "шагоход Закуула"),
    ("Zakuul Army", "армия Закуула"),
    ("Zakuulan", "закуулский"),
    ("Zakuul", "Закуула"),
    ("Occupation Force", "оккупационные силы"),
    ("Security Force", "служба безопасности"),
    ("Special Forces", "спецназ"),
    ("Planetary Defense Force", "планетарные силы обороны"),
    ("Battle Droid Garrison", "гарнизон боевых дроидов"),
    ("Battle Droid Army", "армия боевых дроидов"),
    ("War-Droid Garrison", "гарнизон боевых дроидов"),
    ("War-Droid Army", "армия боевых дроидов"),
    ("Droid Garrison", "гарнизон дроидов"),
    ("Droid Army", "армия дроидов"),
    ("Stormtrooper Legion", "легион штурмовиков"),
    ("Trooper Legion", "легион солдат"),
    ("Trooper Company", "рота солдат"),
    ("Trooper Army", "армия солдат"),
    ("Army Division", "армейская дивизия"),
    ("Army Garrison", "армейский гарнизон"),
    ("Battle Fleet", "боевой флот"),
    ("War Fleet", "военный флот"),
    ("Fleet", "флот"),
    ("Garrison", "гарнизон"),
    ("Army", "армия"),
    ("Division", "дивизия"),
    ("Legion", "легион"),
    ("Battalion", "батальон"),
    ("Company", "рота"),
    ("Squad", "отряд"),
    ("Squadron", "эскадрилья"),
    ("Militia", "ополчение"),
    ("Patriots", "патриоты"),
    ("Supporters", "сторонники"),
    ("Insurgents", "повстанцы"),
    ("Servants", "слуги"),
    ("Warriors", "воины"),
    ("Knights", "рыцари"),
    ("Acolytes", "послушники"),
    ("Assassins", "ассасины"),
    ("Inquisitors", "инквизиторы"),
    ("Sorcerers", "колдуны"),
    ("Juggernauts", "джаггернауты"),
    ("Marauders", "мародёры"),
    ("Commandos", "коммандос"),
    ("Master", "магистр"),
    ("Padawans", "падаваны"),
    ("Guardians", "стражи"),
    ("Sentinels", "часовые"),
    ("Consulars", "консулы"),
    ("Shadows", "тени"),
    ("Sages", "мудрецы"),
    ("Jedi", "джедаев"),
    ("Droids", "дроиды"),
    ("Droid", "дроид"),
    ("Troopers", "солдаты"),
    ("Trooper", "солдат"),
    ("Walkers", "шагоходы"),
    ("Walker", "шагоход"),
    ("Beast Handlers", "укротители зверей"),
    ("Beasts", "звери"),
    ("Horde", "орда"),
    ("Recruits", "рекруты"),
    ("Exiles", "изгнанники"),
    ("Guard", "гвардия"),
    ("Cannon Fodder", "пушечное мясо"),
)


def translate_template(value: str) -> str:
    placeholders = re.findall(r"ZXQ\d{4}T\d{2}QXZ", value)
    phrase = re.sub(r"ZXQ\d{4}T\d{2}QXZ", "", value).strip().strip('"').strip()
    phrase = re.sub(r"\s+", " ", phrase)
    for english, russian in TEMPLATE_REPLACEMENTS:
        phrase = phrase.replace(english, russian)
    phrase = re.sub(r"\s+", " ", phrase).strip()
    if re.search(r"[A-Za-z]{4,}", phrase):
        # Remaining words are generally canonical unit/model names and acronyms.
        phrase = phrase.replace("Dark", "тёмный").replace("Elite", "элитный").replace("Undead", "нежить")
    return (" ".join(placeholders) + " " + phrase).strip()


def import_responses() -> None:
    responses = WORK / "responses"
    translated = WORK / "translated"
    translated.mkdir(exist_ok=True)
    imported = 0
    for response_path in sorted(responses.glob("batch_*.json")):
        try:
            payload = json.loads(response_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Skipping non-JSON response: {response_path.name}")
            continue
        if not payload or not payload[0]:
            raise ValueError(f"Empty translation response: {response_path}")
        if isinstance(payload[0], str):
            text = payload[0]
        else:
            text = "".join(part[0] for part in payload[0] if part and part[0] is not None)
        output_path = translated / response_path.with_suffix(".txt").name
        output_path.write_text(text, encoding="utf-8")
        imported += 1
    print(f"Imported {imported} translation responses")


def prepare_local_prompts(batch_ids: list[int]) -> None:
    prompt_dir = WORK / "local_prompts"
    prompt_dir.mkdir(exist_ok=True)
    instructions = (
        "Translate the following Stellaris mod localization values from English to Russian. "
        "Use established Russian Star Wars terminology and natural concise game UI language. "
        "Return ONLY the translated lines, one line per input line, in the original order. "
        "Preserve every @@SWdddd@@ marker and every ZXQddddTddQXZ placeholder exactly. "
        "Do not use Markdown, comments, explanations, or blank lines.\n\n"
    )
    for batch_id in batch_ids:
        source = WORK / "batches" / f"batch_{batch_id:03d}.txt"
        destination = prompt_dir / f"batch_{batch_id:03d}.txt"
        destination.write_text(instructions + source.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Prepared {len(batch_ids)} local-model prompts")


EXACT_VALUE_FIXES = {
    "Конфедерация": "Конфедерация",
    "Первый заказ": "Первый Орден",
    "Галактическая республика": "Галактическая Республика",
    "Галактическая империя": "Галактическая Империя",
    "Империя ситхов": "Империя ситхов",
    "Древний ситх": "Древние ситхи",
    "Мандалорский": "Мандалорцы",
    "Клон-солдат": "Клон-солдат",
    "Альянс": "Альянс",
    "Дроид": "Дроиды",
    "SW Aliens": "Инопланетяне Star Wars",
    "Trayus Core": "Ядро Трайуса",
    "v-150 Planet Defender": "Планетарная ионная пушка v-150",
    "$ORD$ Organic Decimators": "$ORD$ органические дециматоры",
    "$ORD$ Umbaran Supercommandos": "$ORD$ умбаранские суперкоммандос",
    "$ORD$ Zilo Beast Clone": "$ORD$ клон зверя Зилло",
    "$ORD$ HAVw A6 Juggernaut Tank": "$ORD$ танк-джаггернаут HAVw A6",
    "$ORD$ LAAT/i Attack Gunship": "$ORD$ штурмовой транспорт LAAT/i",
    "$ORD$ Grotthu Thralls": "$ORD$ рабы гротту",
    "$C$ Massassi Tribes": "$C$ племена массасси",
    "$C$ Kissai Caste": "$C$ каста киссаи",
    "$ORD$ Neo-Crusader Armada": "$ORD$ армада неокрестоносцев",
    "$ORD$ Rakghoul Crusaders": "$ORD$ крестоносцы-ракгулы",
    "$ORD$ Mandallian Giants": "$ORD$ мандаллианские гиганты",
    "$ORD$ Project Blackwing": "$ORD$ проект «Чёрное крыло»",
    "$ORD$ Siege Skytrooper": "$ORD$ осадный скайтрупер",
    "$ORD$ Zildrog's Chosen": "$ORD$ избранники Зилдрога",
    "$ORD$ Exarch": "$ORD$ экзарх",
    "$R$ Exarch": "$R$ экзарх",
}

TEXT_FIXES = (
    ("Первого заказа", "Первого Ордена"),
    ("Первый заказ", "Первый Орден"),
    ("Первого Ордена", "Первого Ордена"),
    ("Звездная кузница", "Звёздная кузница"),
    ("Звездной кузницы", "Звёздной кузницы"),
    ("Звездную кузницу", "Звёздную кузницу"),
    ("Звездной Кузницы", "Звёздной кузницы"),
    ("Звездная Кузница", "Звёздная кузница"),
    ("Star Forge", "Звёздная кузница"),
    ("Kuat Drive Yards", "Верфи Куата"),
    ("The Ten", "Десятка"),
    ("§YDroids §!", "§YДроиды§!"),
    ("§YMachine Template System§!", "§YСистема шаблонов машин§!"),
    ("рыцари of Ren", "рыцари Рен"),
    ("звери of Zildrog", "звери Зилдрога"),
    ("рыцари of Закуула", "рыцари Закуула"),
    ("Scions of Закуула", "наследники Закуула"),
    ("Корускант", "Корусант"),
    ("Корусскант", "Корусант"),
    ("Дромунд Каас", "Дромунд-Каас"),
    ("Темный совет", "Тёмный совет"),
    ("Темного совета", "Тёмного совета"),
    ("Темной стороны", "тёмной стороны"),
    ("темной стороны", "тёмной стороны"),
    ("Светлой стороны", "светлой стороны"),
    ("Галактическая республика", "Галактическая Республика"),
    ("Галактической республики", "Галактической Республики"),
    ("Галактическая империя", "Галактическая Империя"),
    ("Галактической империи", "Галактической Империи"),
    ("Старая республика", "Старая Республика"),
    ("Старой республики", "Старой Республики"),
    ("Новая республика", "Новая Республика"),
    ("Новой республики", "Новой Республики"),
    ("Альянс повстанцев", "Альянс повстанцев"),
    ("Ракатан", "ракатан"),
    ("джедайский", "джедайский"),
)


def polish(value: str) -> str:
    value = EXACT_VALUE_FIXES.get(value, value)
    for old, new in TEXT_FIXES:
        value = value.replace(old, new)
    value = re.sub(r"[ \t]+", " ", value).strip()
    return value


def assemble() -> None:
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    translations = read_translations()
    for item in manifest:
        index = int(item["index"])
        if index >= 1825 and index not in translations:
            translations[index] = translate_template(str(item["protected"]))
    missing = [item["index"] for item in manifest if item["index"] not in translations]
    if missing:
        raise ValueError(f"Missing translated items: {missing[:20]} ({len(missing)} total)")

    output = ["l_russian:", ""]
    for item in manifest:
        index = int(item["index"])
        value = translations[index]
        for placeholder, token in item["tokens"].items():
            if placeholder not in value:
                raise ValueError(f"Placeholder {placeholder} missing after translation of {item['key']}")
            value = value.replace(placeholder, token)
        value = polish(value).replace('"', '\\"')
        output.append(f" {item['key']}: \"{value}\"")

    LOCALE.mkdir(parents=True, exist_ok=True)
    CORE_OUT.write_text("\ufeff" + "\n".join(output) + "\n", encoding="utf-8")
    print(f"Wrote {CORE_OUT} with {len(manifest)} keys")


def extract_tokens(value: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(value.replace('\\\\"', '\\"')))


def validate() -> None:
    source = {str(item["key"]): str(item["value"]) for item in parse_source()}
    lines = CORE_OUT.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "l_russian:":
        raise ValueError("Invalid localization header")
    translated: dict[str, str] = {}
    for line_no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ENTRY_RE.match(line)
        if not match:
            raise ValueError(f"Invalid output line {line_no}: {line}")
        key = match.group(1).strip()
        if key in translated:
            raise ValueError(f"Duplicate output key: {key}")
        translated[key] = match.group(2)
    if source.keys() != translated.keys():
        raise ValueError(f"Coverage mismatch: missing={source.keys()-translated.keys()}, extra={translated.keys()-source.keys()}")
    mismatches = [key for key in source if extract_tokens(source[key]) != extract_tokens(translated[key])]
    if mismatches:
        raise ValueError(f"Token mismatches: {mismatches[:20]} ({len(mismatches)} total)")
    cyrillic = sum(bool(re.search(r"[А-Яа-яЁё]", value)) for value in translated.values())
    identical = sum(source[key] == translated[key] for key in source)
    print(f"Validated {len(translated)} keys; Cyrillic values={cyrillic}; unchanged values={identical}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--batch-chars", type=int, default=3800)
    sub.add_parser("import-responses")
    local_parser = sub.add_parser("prepare-local-prompts")
    local_parser.add_argument("batch_ids", nargs="+", type=int)
    sub.add_parser("assemble")
    sub.add_parser("validate")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.batch_chars)
    elif args.command == "import-responses":
        import_responses()
    elif args.command == "prepare-local-prompts":
        prepare_local_prompts(args.batch_ids)
    elif args.command == "assemble":
        assemble()
    elif args.command == "validate":
        validate()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise
