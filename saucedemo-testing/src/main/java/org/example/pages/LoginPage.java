package org.example.pages;

import org.example.config.ConfigReader;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class LoginPage extends BasePage {

    private static final By USERNAME_INPUT = By.id("user-name");
    private static final By PASSWORD_INPUT = By.id("password");
    private static final By LOGIN_BUTTON = By.id("login-button");
    private static final By ERROR_MESSAGE = By.cssSelector("h3[data-test='error']");

    public LoginPage(WebDriver driver) {
        super(driver);
    }

    public LoginPage open() {
        driver.get(ConfigReader.get("base.url"));
        return this;
    }

    public InventoryPage loginAs(String username, String password) {
        waitForVisible(USERNAME_INPUT).sendKeys(username);
        waitForVisible(PASSWORD_INPUT).sendKeys(password);
        click(LOGIN_BUTTON);
        return new InventoryPage(driver);
    }

    public String getErrorMessage() {
        return getText(ERROR_MESSAGE);
    }

    public boolean isErrorDisplayed() {
        return waitForVisible(ERROR_MESSAGE).isDisplayed();
    }
}