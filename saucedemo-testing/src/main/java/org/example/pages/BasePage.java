package org.example.pages;

import org.example.config.ConfigReader;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;

public abstract class BasePage {

    protected static final Logger log = LoggerFactory.getLogger(BasePage.class);

    protected final WebDriver driver;
    protected final WebDriverWait wait;

    protected BasePage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver,
                Duration.ofSeconds(ConfigReader.getInt("explicit.wait")));
    }

    /**
     * Открывает URL с retry — защищает от временных сетевых сбоев
     * (например, ERR_CONNECTION_RESET при первом обращении к сайту).
     * Делает до 3 попыток с паузой 2 секунды между ними.
     */
    protected void navigateTo(String url) {
        int attempts = 3;
        for (int i = 1; i <= attempts; i++) {
            try {
                driver.get(url);
                return;
            } catch (Exception e) {
                log.warn("Попытка {} из {} открыть {} не удалась: {}",
                        i, attempts, url, e.getMessage());
                if (i == attempts) {
                    throw new RuntimeException(
                            "Не удалось открыть " + url + " после " + attempts + " попыток", e);
                }
                try {
                    Thread.sleep(2000);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                }
            }
        }
    }

    protected WebElement waitForVisible(By locator) {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
    }

    protected WebElement waitForClickable(By locator) {
        return wait.until(ExpectedConditions.elementToBeClickable(locator));
    }

    protected void click(By locator) {
        waitForClickable(locator).click();
    }

    protected String getText(By locator) {
        return waitForVisible(locator).getText();
    }

    public String getTitle() {
        return driver.getTitle();
    }

    public String getCurrentUrl() {
        return driver.getCurrentUrl();
    }
}