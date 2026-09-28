package org.example.tests;

import org.example.pages.CartPage;
import org.example.pages.CheckoutCompletePage;
import org.example.pages.CheckoutPage;
import org.example.pages.InventoryPage;
import org.example.pages.LoginPage;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("e2e")
public class PurchaseE2ETest extends BaseTest {

    @Test
    @DisplayName("E2E: Полный сценарий покупки от логина до подтверждения заказа")
    void fullPurchaseFlow() {
        log.info("Шаг 1: Логин");
        InventoryPage inventory = new LoginPage(driver)
                .open()
                .loginAs("standard_user", "secret_sauce");

        Assertions.assertEquals("Products", inventory.getPageTitle(),
                "После логина должна открыться страница каталога");

        log.info("Шаг 2: Добавляем два товара в корзину");
        inventory.addToCart("Sauce Labs Backpack");
        inventory.addToCart("Sauce Labs Bolt T-Shirt");

        String badge = inventory.getCartBadgeCount();
        log.info("Счётчик корзины после добавления двух товаров: '{}'", badge);
        Assertions.assertEquals("2", badge,
                "Счётчик должен показывать '2' после добавления двух товаров");

        log.info("Шаг 3: Переходим в корзину");
        CartPage cart = inventory.goToCart();
        log.info("URL корзины: {}", driver.getCurrentUrl());

        boolean hasBackpack = cart.isProductInCart("Sauce Labs Backpack");
        log.info("Backpack в корзине: {}", hasBackpack);

        boolean hasTShirt = cart.isProductInCart("Sauce Labs Bolt T-Shirt");
        log.info("Bolt T-Shirt в корзине: {}", hasTShirt);

        Assertions.assertTrue(hasBackpack, "Первый товар должен быть в корзине");
        Assertions.assertTrue(hasTShirt, "Второй товар должен быть в корзине");

        log.info("Шаг 4: Оформляем заказ");
        CheckoutPage checkout = cart.goToCheckout();
        CheckoutCompletePage complete = checkout
                .fillCustomerInfo("Иван", "Петров", "123456")
                .continueToOverview()
                .finishOrder();

        log.info("Шаг 5: Проверяем подтверждение");
        String message = complete.getConfirmationMessage();
        Assertions.assertTrue(message.contains("Thank you for your order"),
                "Должно появиться подтверждение заказа, но было: " + message);

        log.info("E2E-сценарий успешно завершён");
    }
}