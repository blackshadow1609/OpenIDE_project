package org.example.tests;

import org.example.pages.CartPage;
import org.example.pages.InventoryPage;
import org.example.pages.LoginPage;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

public class CartTest extends BaseTest {

    private InventoryPage loginAndGoToInventory() {
        return new LoginPage(driver)
                .open()
                .loginAs("standard_user", "secret_sauce");
    }

    @Test
    @DisplayName("Добавление товара в корзину увеличивает счётчик")
    void addToCartUpdatesBadge() {
        InventoryPage inventory = loginAndGoToInventory();

        inventory.addToCart("Sauce Labs Backpack");
        String badge = inventory.getCartBadgeCount();

        log.info("Счётчик корзины: {}", badge);
        Assertions.assertEquals("1", badge,
                "После добавления одного товара счётчик должен быть '1'");
    }

    @Test
    @DisplayName("Добавленный товар отображается в корзине")
    void addedProductAppearsInCart() {
        String productName = "Sauce Labs Bike Light";

        InventoryPage inventory = loginAndGoToInventory();
        inventory.addToCart(productName);
        CartPage cart = inventory.goToCart();

        Assertions.assertTrue(cart.isProductInCart(productName),
                "Товар '" + productName + "' должен быть в корзине");
        log.info("Товар '{}' успешно найден в корзине", productName);
    }

    @Test
    @DisplayName("Сортировка товаров по имени (Z → A) работает")
    void sortByNameDescending() {
        InventoryPage inventory = loginAndGoToInventory();
        inventory.sortBy("Name (Z to A)");

        var names = inventory.getProductNames();
        log.info("Первый товар после сортировки: {}", names.get(0));

        Assertions.assertEquals("Test.allTheThings() T-Shirt (Red)", names.get(0),
                "Первым должен быть товар, начинающийся на 'T'");
    }
}