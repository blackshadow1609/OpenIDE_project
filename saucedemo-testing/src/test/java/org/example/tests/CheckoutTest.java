package org.example.tests;

import org.example.pages.CartPage;
import org.example.pages.CheckoutCompletePage;
import org.example.pages.CheckoutPage;
import org.example.pages.InventoryPage;
import org.example.pages.LoginPage;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

public class CheckoutTest extends BaseTest {

    private CartPage loginAddProductAndGoToCart() {
        InventoryPage inventory = new LoginPage(driver)
                .open()
                .loginAs("standard_user", "secret_sauce");
        inventory.addToCart("Sauce Labs Backpack");
        return inventory.goToCart();
    }

    @Test
    @DisplayName("Успешное оформление заказа")
    void successfulCheckout() {
        CartPage cart = loginAddProductAndGoToCart();
        CheckoutPage checkout = cart.goToCheckout();

        CheckoutCompletePage complete = checkout
                .fillCustomerInfo("Иван", "Петров", "123456")
                .continueToOverview()
                .finishOrder();

        String message = complete.getConfirmationMessage();
        log.info("Сообщение подтверждения: {}", message);

        Assertions.assertTrue(message.contains("Thank you for your order"),
                "Сообщение подтверждения должно содержать 'Thank you for your order', но было: " + message);
    }

    @Test
    @DisplayName("Checkout без имени показывает ошибку валидации")
    void checkoutWithoutFirstNameShowsError() {
        CartPage cart = loginAddProductAndGoToCart();
        CheckoutPage checkout = cart.goToCheckout();

        checkout.fillCustomerInfo("", "Петров", "123456")
                .continueWithInvalidData();

        String currentUrl = driver.getCurrentUrl();
        log.info("Текущий URL после Continue: {}", currentUrl);

        Assertions.assertTrue(currentUrl.contains("checkout-step-one"),
                "После ошибки валидации URL должен оставаться на шаге checkout-step-one, но был: " + currentUrl);
    }
}