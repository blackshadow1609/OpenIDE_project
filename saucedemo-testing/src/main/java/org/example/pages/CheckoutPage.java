package org.example.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CheckoutPage extends BasePage {

    private static final Logger log = LoggerFactory.getLogger(CheckoutPage.class);

    private static final By FIRST_NAME = By.id("first-name");
    private static final By LAST_NAME = By.id("last-name");
    private static final By POSTAL_CODE = By.id("postal-code");
    private static final By CONTINUE_BUTTON = By.id("continue");
    private static final By FINISH_BUTTON = By.id("finish");

    public CheckoutPage(WebDriver driver) {
        super(driver);
    }

    public CheckoutPage fillCustomerInfo(String firstName, String lastName, String postalCode) {
        log.info("Заполняю форму: firstName='{}', lastName='{}', postalCode='{}'",
                firstName, lastName, postalCode);

        typeInto(FIRST_NAME, firstName, "First Name");
        typeInto(LAST_NAME, lastName, "Last Name");
        typeInto(POSTAL_CODE, postalCode, "Postal Code");

        return this;
    }

    private void typeInto(By locator, String value, String fieldName) {
        WebElement field = waitForVisible(locator);
        field.clear();

        if (!value.isEmpty()) {
            click(locator);
            try {
                Thread.sleep(200);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }

            try {
                field = driver.findElement(locator);
                field.clear();

                // Посимвольный ввод — стабильнее, чем sendKeys всей строкой
                for (char c : value.toCharArray()) {
                    field.sendKeys(String.valueOf(c));
                    try {
                        Thread.sleep(30);
                    } catch (InterruptedException ignored) {
                        Thread.currentThread().interrupt();
                    }
                }

                long deadline = System.currentTimeMillis() + 5_000;
                while (System.currentTimeMillis() < deadline) {
                    String actual = field.getAttribute("value");
                    if (value.equals(actual)) {
                        log.debug("{} заполнено через sendKeys: '{}'", fieldName, actual);
                        return;
                    }
                    try {
                        Thread.sleep(100);
                    } catch (InterruptedException ignored) {
                        Thread.currentThread().interrupt();
                    }
                }
                throw new RuntimeException("sendKeys не применил значение");
            } catch (Exception e) {
                log.warn("sendKeys не сработал для '{}': {} — использую JavaScript fallback",
                        fieldName, e.getMessage());

                JavascriptExecutor js = (JavascriptExecutor) driver;
                js.executeScript(
                        "var field = arguments[0];" +
                                "var value = arguments[1];" +
                                "var nativeInputValueSetter = Object.getOwnPropertyDescriptor(" +
                                "    window.HTMLInputElement.prototype, 'value').set;" +
                                "nativeInputValueSetter.call(field, value);" +
                                "field.dispatchEvent(new Event('input', { bubbles: true }));" +
                                "field.dispatchEvent(new Event('change', { bubbles: true }));",
                        field, value);

                log.debug("{} заполнено через JavaScript: '{}'", fieldName, field.getAttribute("value"));
            }
        } else {
            log.debug("{} оставлено пустым", fieldName);
        }
    }

    public CheckoutPage continueToOverview() {
        log.info("Кликаю Continue (ожидаю переход на Overview). URL до клика: {}",
                driver.getCurrentUrl());
        click(CONTINUE_BUTTON);
        wait.until(d -> d.getCurrentUrl().contains("checkout-step-two"));
        log.info("Перешли на шаг Overview: {}", driver.getCurrentUrl());
        return this;
    }

    public CheckoutPage continueWithInvalidData() {
        log.info("Кликаю Continue (ожидаю ошибку валидации). URL до клика: {}",
                driver.getCurrentUrl());
        click(CONTINUE_BUTTON);
        return this;
    }

    public CheckoutCompletePage finishOrder() {
        log.info("Кликаю Finish. Текущий URL: {}", driver.getCurrentUrl());
        click(FINISH_BUTTON);
        // Ждём переход на страницу подтверждения
        wait.until(d -> d.getCurrentUrl().contains("checkout-complete"));
        log.info("Перешли на страницу подтверждения: {}", driver.getCurrentUrl());
        return new CheckoutCompletePage(driver);
    }
}