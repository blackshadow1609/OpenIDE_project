package org.example.pages;

import org.openqa.selenium.By;
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

    /**
     * Вводит текст в поле и явно ждёт, что значение применилось.
     * Защищает от race condition: sendKeys() возвращает управление до того,
     * как браузер обработал ввод, и getAttribute("value") может вернуть пустоту.
     */
    private void typeInto(By locator, String value, String fieldName) {
        WebElement field = waitForVisible(locator);
        field.clear();
        field.sendKeys(value);

        wait.until(d -> value.equals(d.findElement(locator).getAttribute("value")));

        log.debug("{} заполнено: '{}'", fieldName, field.getAttribute("value"));
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
        return new CheckoutCompletePage(driver);
    }
}