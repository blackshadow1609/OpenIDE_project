package org.example.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CartPage extends BasePage {

    private static final Logger log = LoggerFactory.getLogger(CartPage.class);

    private static final By PAGE_TITLE = By.className("title");
    private static final By CHECKOUT_BUTTON = By.id("checkout");
    private static final By CONTINUE_SHOPPING_BUTTON = By.id("continue-shopping");

    public CartPage(WebDriver driver) {
        super(driver);
    }

    public String getPageTitle() {
        return getText(PAGE_TITLE);
    }

    /**
     * Проверяет наличие товара в корзине, ожидая его появления до 10 секунд.
     * Возвращает false, если товар так и не появился.
     */
    public boolean isProductInCart(String productName) {
        By productLocator = By.xpath(
                String.format("//div[@class='inventory_item_name' and text()='%s']", productName));
        try {
            wait.until(d -> !d.findElements(productLocator).isEmpty());
            return true;
        } catch (Exception e) {
            log.warn("Товар '{}' не найден в корзине за отведённое время", productName);
            return false;
        }
    }

    /**
     * Кликает по Checkout и ждёт, что URL сменился на checkout-step-one.
     * Без этого ожидания следующий шаг (fillCustomerInfo) может пытаться
     * найти поля формы, пока страница ещё не загрузилась.
     */
    public CheckoutPage goToCheckout() {
        log.info("Кликаю Checkout. URL до клика: {}", driver.getCurrentUrl());
        click(CHECKOUT_BUTTON);

        wait.until(d -> d.getCurrentUrl().contains("checkout-step-one"));

        log.info("Перешли на страницу Checkout: {}", driver.getCurrentUrl());
        return new CheckoutPage(driver);
    }

    public InventoryPage continueShopping() {
        click(CONTINUE_SHOPPING_BUTTON);
        return new InventoryPage(driver);
    }
}