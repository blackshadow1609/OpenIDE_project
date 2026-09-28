# Saucedemo UI Automation Tests

Автоматизированные UI- и E2E-тесты для интернет-магазина [saucedemo.com](https://www.saucedemo.com/) на Java + Selenium WebDriver + JUnit 5.

[![Tests](https://img.shields.io/badge/tests-8%20passed-brightgreen)]()
[![Success Rate](https://img.shields.io/badge/success%20rate-100%25-brightgreen)]()
[![Java](https://img.shields.io/badge/Java-21-blue)]()
[![Selenium](https://img.shields.io/badge/Selenium-4.27.0-green)]()

## 🎯 Что тестируется

Saucedemo — учебный интернет-магазин с полным циклом покупки: логин → каталог → корзина → оформление заказа → подтверждение.

Проект покрывает **8 тестов** в **4 классах**:

| Тип | Класс | Тестов | Что проверяет |
|-----|-------|--------|---------------|
| Smoke + Functional | `LoginTest` | 2 | Успешный вход, ошибка при неверном пароле |
| Functional | `CartTest` | 3 | Добавление товара, отображение в корзине, сортировка |
| Functional | `CheckoutTest` | 2 | Оформление заказа, валидация формы |
| E2E | `PurchaseE2ETest` | 1 | Полный сценарий покупки от логина до подтверждения |

**Результат прогона:** ✅ 8 из 8 тестов зелёные, Success Rate — **100%**, время — ~28 секунд.

## 🛠️ Технологический стек

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| Java | 21 (LTS) | Язык разработки |
| Selenium WebDriver | 4.27.0 | Управление браузером |
| JUnit 5 | 5.11.4 | Тестовый фреймворк |
| Maven | 3.8+ | Сборка и управление зависимостями |
| SLF4J + Logback | 2.0.16 / 1.5.12 | Логирование |
| Surefire Report | 3.5.2 | HTML-отчёт о тестах |
| Chrome / Firefox / Edge | — | Целевые браузеры |

## 🏗️ Архитектура

Проект построен по паттерну **Page Object Model (POM)** — каждая страница приложения представлена отдельным классом с локаторами и действиями. Тесты не работают с локаторами напрямую — они вызывают методы Page Object'ов.


### Ключевые особенности

- **Page Object Model** — локаторы и действия отделены от логики тестов.
- **Конфигурируемость** — браузер, URL, таймауты задаются в `config.properties` без правки кода.
- **Скриншоты при падении** — автоматически сохраняются в `target/screenshots/`.
- **Структурированное логирование** — все действия записываются в `target/logs/tests.log` через SLF4J + Logback.
- **HTML-отчёт** — генерируется через `maven-surefire-report-plugin` в `target/site/surefire-report.html`.
- **Fluent Interface** — цепочки вызовов `loginAs(...).addToCart(...).goToCart()` читаются как обычный текст.
- **Явные ожидания** — `WebDriverWait` вместо `Thread.sleep` для стабильности тестов.
- **Retry при навигации** — устойчивость к временным сетевым сбоям.
- **Headless-режим** — можно запускать без GUI, для CI/CD.

## 🚀 Запуск тестов

### Требования

- JDK 21+
- Google Chrome (последняя версия)
- Maven 3.8+

