package org.example.tests;

import org.example.pages.InventoryPage;
import org.example.pages.LoginPage;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

public class LoginTest extends BaseTest {

    @Test
    @DisplayName("Успешный вход в систему")
    void successfulLogin() {
        InventoryPage inventory = new LoginPage(driver)
                .open()
                .loginAs("standard_user", "secret_sauce");

        String title = inventory.getPageTitle();
        log.info("Заголовок страницы: {}", title);
        Assertions.assertEquals("Products", title, "Заголовок не совпадает");
    }

    @Test
    @DisplayName("Вход с неверным паролем показывает ошибку")
    void loginWithInvalidPassword() {
        LoginPage loginPage = new LoginPage(driver).open();
        loginPage.loginAs("standard_user", "wrong_password");

        Assertions.assertTrue(loginPage.isErrorDisplayed(), "Сообщение об ошибке не появилось");
        log.info("Текст ошибки: {}", loginPage.getErrorMessage());
    }
}