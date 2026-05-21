from __future__ import annotations

from typing import Any

from app.schemas import NewsAnalyzeResponse
from app.services.ollama_client import OllamaClient


SYSTEM_PROMPT = """
Ты финансовый AI-аналитик российского фондового рынка.
Твоя задача: классифицировать событие и оценить возможное влияние на акции МосБиржи, ОФЗ, рубль, сектора и дивиденды.
Отвечай строго JSON без markdown.

Схема JSON:
{
  "event_type": "dividends|rates|bonds|fx|banking|consumer_finance|sanctions|earnings|regulation|commodities|corporate_action|macro|other",
  "importance": 1-10,
  "impact": "positive|negative|mixed|neutral|uncertain",
  "affected_assets": ["SBER", "GAZP", "IMOEX", "OFZ", "RUB"],
  "affected_sectors": ["банки", "нефтегаз"],
  "time_horizon": "intraday|1-7d|1-4w|1-3m|6m+",
  "confidence": 0.0-1.0,
  "reasoning": "короткое объяснение по-русски",
  "watch_next": ["что отслеживать дальше"]
}
""".strip()


class EventClassifier:
    async def analyze(self, text: str, title: str | None = None) -> NewsAnalyzeResponse:
        user = f"Заголовок: {title or ''}\nТекст события: {text}"
        try:
            data = await OllamaClient().generate_json(SYSTEM_PROMPT, user)
            return self._normalize_response(data, title=title)
        except Exception:
            return self._fallback(text, title=title)

    def _normalize_response(self, data: dict[str, Any], title: str | None = None) -> NewsAnalyzeResponse:
        return NewsAnalyzeResponse(
            title=title,
            event_type=str(data.get("event_type", "other")),
            importance=max(1, min(10, int(data.get("importance", 5)))),
            impact=str(data.get("impact", "uncertain")),
            affected_assets=list(data.get("affected_assets") or []),
            affected_sectors=list(data.get("affected_sectors") or []),
            time_horizon=str(data.get("time_horizon", "1-4w")),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=str(data.get("reasoning", "Недостаточно данных для уверенного вывода.")),
            watch_next=list(data.get("watch_next") or []),
        )

    def _fallback(self, text: str, title: str | None = None) -> NewsAnalyzeResponse:
        full_text = f"{title or ''}. {text or ''}".lower()

        assets: list[str] = []
        sectors: list[str] = []

        event_type = "other"
        impact = "uncertain"
        importance = 4
        time_horizon = "1-4w"
        watch_next = [
            "официальные комментарии регулятора или эмитента",
            "реакцию котировок",
            "объём торгов",
        ]

        self._add_ticker_mentions(full_text, assets)

        # 1. Нерелевантные или низкорыночные новости ЦБ
        if self._has_any(full_text, ["монет", "памятн", "нумизмат", "банкнот", "наличн"]):
            event_type = "other"
            importance = 2
            impact = "neutral"
            watch_next = ["рыночной реакции обычно не требуется"]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Новость выглядит операционной/информационной и обычно не оказывает прямого влияния на рынок."
            )

        # 2. Геополитика, военные риски и нефтяной shock
        if self._has_any(full_text, [
            "иран",
            "сша",
            "ормуз",
            "персидский залив",
            "ближний восток",
            "военная операция",
            "удар",
            "ракета",
            "эскалац",
            "конфликт",
            "геополит",
        ]):
            event_type = "geopolitical"
            importance = 9
            impact = "mixed"
            self._extend_unique(assets, ["IMOEX", "RUB", "LKOH", "ROSN", "TATN", "SNGS", "GAZP", "NVTK", "AFLT", "PLZL"])
            self._extend_unique(sectors, ["нефтегаз", "авиаперевозки", "золото", "широкий рынок"])
            watch_next = [
                "цены на нефть Brent",
                "заявления США/Ирана",
                "риск перекрытия Ормузского пролива",
                "реакцию рубля",
                "динамику нефтегаза и авиаперевозчиков",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Новость указывает на геополитический риск: нефтегаз может получить поддержку от роста нефти, авиаперевозчики — давление, широкий рынок — risk-off, золото — защитный спрос."
            )

        # 3. Санкции: снятие/смягчение и ужесточение
        if self._has_any(full_text, ["снятие санкций", "смягчение санкций", "отмена ограничений", "исключили из санкционного списка"]):
            event_type = "sanctions"
            importance = 9
            impact = "positive"
            self._extend_unique(assets, ["SBER", "VTBR", "MOEX", "SPBE", "IMOEX", "RUB"])
            self._extend_unique(sectors, ["банки", "биржи", "широкий рынок", "логистика"])
            watch_next = [
                "официальные формулировки санкционных решений",
                "реакцию банков и биржевой инфраструктуры",
                "динамику рубля",
                "оценку риск-премии российских активов",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Смягчение санкций снижает риск-премию РФ и поддерживает банки, биржи, рубль и широкий рынок."
            )

        if self._has_any(full_text, ["новые санкции", "расширение санкций", "sdn", "экспортный контроль", "ограничения против рф"]):
            event_type = "sanctions"
            importance = 9
            impact = "negative"
            self._extend_unique(assets, ["SBER", "VTBR", "MOEX", "SPBE", "IMOEX", "RUB"])
            self._extend_unique(sectors, ["банки", "биржи", "экспортёры", "широкий рынок"])
            watch_next = [
                "перечень новых ограничений",
                "реакцию контрагентов",
                "динамику рубля",
                "операционные комментарии эмитентов",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Усиление санкций повышает риск-премию РФ и негативно для банков, биржевой инфраструктуры, экспортёров и широкого рынка."
            )

        # 4. Ключевая ставка и денежно-кредитная политика
        if (
            self._has_all(full_text, ["ключев", "ставк"])
            or self._has_any(full_text, ["денежно-кредитн", "дкп"])
            or self._has_any(full_text, ["заседание совета директоров банка россии по ключевой ставке"])
        ):
            event_type = "rates"
            importance = 9
            rate_down = self._has_any(full_text, ["сниз", "пониз", "смягч", "ниже"])
            rate_up = self._has_any(full_text, ["повыс", "ужесточ", "выше"])
            impact = "positive" if rate_down else "negative" if rate_up else "mixed"
            self._extend_unique(assets, ["OFZ", "RUB", "IMOEX", "SBER", "VTBR", "PIKK", "SMLT", "LSRG", "ETLN"])
            self._extend_unique(sectors, ["облигации", "банки", "девелоперы", "rate-sensitive", "дивидендные акции"])
            watch_next = [
                "сигнал ЦБ по будущей траектории ставки",
                "доходности ОФЗ",
                "инфляционные ожидания",
                "реакцию банков и девелоперов",
            ]
            if rate_down:
                reasoning = "ЦБ снизил ключевую ставку: это поддерживает ОФЗ, девелоперов и другие rate-sensitive активы, а для банков эффект умеренно положительный или смешанный."
            elif rate_up:
                reasoning = "ЦБ повысил ключевую ставку: это давит на ОФЗ, девелоперов и широкий рынок; для банков эффект смешанный, без автоматического сильного boost."
            else:
                reasoning = "Событие связано с ключевой ставкой или ДКП, но направление неочевидно; влияние на ОФЗ, рубль, банки, девелоперов и акции смешанное."
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                reasoning
            )

        # 5. Процентные ставки банков / кредитный рынок
        if (
            self._has_all(full_text, ["процентн", "ставк"])
            and self._has_any(full_text, ["кредитн", "банк", "вклад", "депозит"])
        ):
            event_type = "banking"
            importance = 7
            impact = "mixed"
            self._extend_unique(assets, ["SBER", "VTBR", "OFZ", "RUB"])
            self._extend_unique(sectors, ["банки", "потребительское кредитование"])
            watch_next = [
                "динамику ставок по кредитам и депозитам",
                "маржу банков",
                "спрос на кредиты",
                "доходности ОФЗ",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Новость связана с банковскими ставками и кредитным рынком, поэтому важна для банковского сектора и долгового рынка."
            )

        # 6. Облигации и долговой рынок
        if self._has_any(full_text, ["офз", "облигац", "купон", "доходност", "корпоративные облигации"]):
            event_type = "bonds"
            importance = 6
            impact = "mixed"
            self._extend_unique(assets, ["OFZ", "RUB", "IMOEX"])
            self._extend_unique(sectors, ["облигации", "дивидендные акции", "банки"])
            watch_next = [
                "доходности ОФЗ",
                "спреды корпоративных облигаций",
                "перетоки между облигациями и акциями",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Событие связано с долговым рынком и может влиять на привлекательность ОФЗ, корпоративных облигаций и дивидендных акций."
            )

        # 7. Валюта, рубль, свопы, валютная ликвидность
        if self._has_any(full_text, ["валют", "рубл", "доллар", "юан", "своп", "курс", "cny", "usd"]):
            event_type = "fx"
            importance = 7
            impact = "mixed"
            self._extend_unique(assets, ["RUB", "CNYRUB", "USDRUB"])
            self._extend_unique(sectors, ["экспортёры", "импортёры"])
            watch_next = [
                "динамику рубля",
                "валютную ликвидность",
                "реакцию экспортёров и импортёров",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Новость связана с валютой, рублём или валютной ликвидностью, поэтому важна для FX и компаний с валютной выручкой или импортными затратами."
            )

        # 8. Макропруденциальное регулирование
        if self._has_any(full_text, ["макропруденц", "надбавк", "норматив", "капитал", "резервирован"]):
            event_type = "regulation"
            importance = 8
            impact = "mixed"
            self._extend_unique(assets, ["SBER", "VTBR", "IMOEX"])
            self._extend_unique(sectors, ["банки", "девелоперы", "кредитование"])
            watch_next = [
                "изменения нормативов",
                "влияние на кредитование",
                "комментарии банков",
                "реакцию банковских акций",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Событие связано с регулированием финансового сектора и может влиять на банки, кредитование и чувствительные к ставкам отрасли."
            )

        # 9. Ипотека, качество обслуживания кредитов, жалобы
        if self._has_any(full_text, ["ипотеч", "ипотек", "жалоб", "мфо", "страховщик", "обслуживан"]):
            event_type = "consumer_finance"
            importance = 5
            impact = "uncertain"
            self._extend_unique(assets, ["SBER", "VTBR"])
            self._extend_unique(sectors, ["банки", "страхование", "потребительское кредитование"])
            watch_next = [
                "качество кредитного портфеля",
                "регуляторные ограничения",
                "динамику ипотечного спроса",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Новость относится к потребительскому финансированию, качеству кредитов или клиентским жалобам; влияние на рынок обычно косвенное."
            )

        # 10. Дивиденды
        if self._has_any(full_text, ["дивид", "реестр акционеров", "дивидендн"]):
            event_type = "dividends"
            importance = 8
            impact = "positive" if self._has_any(full_text, ["выше", "рост", "рекоменд", "утверд", "объяв"]) else "mixed"
            watch_next = [
                "дату закрытия реестра",
                "решение собрания акционеров",
                "дивидендную доходность",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Событие связано с дивидендами, что может напрямую влиять на спрос на бумагу и дивидендную доходность."
            )

        # 11. Санкции
        if self._has_any(full_text, ["санкц", "ограничен", "sdn", "экспортный контроль"]):
            event_type = "sanctions"
            importance = 9
            impact = "negative"
            watch_next = [
                "перечень ограничений",
                "реакцию контрагентов",
                "операционные комментарии компании",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Событие связано с санкционными или внешними ограничениями, что может создавать операционные и финансовые риски."
            )

        # 12. Отчётность
        if self._has_any(full_text, ["отчет", "отчёт", "мсфо", "рсбу", "выручк", "прибыл", "ebitda"]):
            event_type = "earnings"
            importance = 7
            impact = "mixed"
            watch_next = [
                "динамику выручки",
                "прибыль и свободный денежный поток",
                "дивидендную базу",
            ]
            return self._response(
                title, event_type, importance, impact, assets, sectors,
                time_horizon, watch_next,
                "Событие похоже на финансовую отчётность или операционные результаты компании."
            )

        return self._response(
            title, event_type, importance, impact, assets, sectors,
            time_horizon, watch_next,
            "Использован локальный rule-based анализ. Событие не попало в специальные категории."
        )

    def _response(
        self,
        title: str | None,
        event_type: str,
        importance: int,
        impact: str,
        assets: list[str],
        sectors: list[str],
        time_horizon: str,
        watch_next: list[str],
        reasoning: str,
    ) -> NewsAnalyzeResponse:
        return NewsAnalyzeResponse(
            title=title,
            event_type=event_type,
            importance=max(1, min(10, int(importance))),
            impact=impact,
            affected_assets=sorted(set(assets)),
            affected_sectors=sorted(set(sectors)),
            time_horizon=time_horizon,
            confidence=0.62,
            reasoning=reasoning,
            watch_next=watch_next,
        )

    def _add_ticker_mentions(self, lower: str, assets: list[str]) -> None:
        mapping = {
            "сбер": "SBER",
            "sber": "SBER",
            "газпром": "GAZP",
            "gazp": "GAZP",
            "лукойл": "LKOH",
            "lkoh": "LKOH",
            "яндекс": "YDEX",
            "ydex": "YDEX",
            "норникель": "GMKN",
            "gmkn": "GMKN",
            "втб": "VTBR",
            "vtbr": "VTBR",
            "мосбирж": "MOEX",
            "moex": "MOEX",
            "татнефт": "TATN",
            "tatn": "TATN",
            "роснефт": "ROSN",
            "rosn": "ROSN",
            "новатэк": "NVTK",
            "nvtk": "NVTK",
            "полюс": "PLZL",
            "plzl": "PLZL",
        }

        for keyword, ticker in mapping.items():
            if keyword in lower and ticker not in assets:
                assets.append(ticker)

    def _has_any(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _has_all(self, text: str, keywords: list[str]) -> bool:
        return all(keyword in text for keyword in keywords)

    def _extend_unique(self, target: list[str], values: list[str]) -> None:
        for value in values:
            if value not in target:
                target.append(value)
