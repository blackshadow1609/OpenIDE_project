package org.example.utils;

import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.TestWatcher;
import org.openqa.selenium.WebDriver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Path;
import java.util.Optional;

public class ScreenshotOnFailureExtension implements TestWatcher {

    private static final Logger log = LoggerFactory.getLogger(ScreenshotOnFailureExtension.class);
    private static final ThreadLocal<WebDriver> DRIVER = new ThreadLocal<>();

    public static void setDriver(WebDriver driver) {
        DRIVER.set(driver);
    }

    public static WebDriver getDriver() {
        return DRIVER.get();
    }

    @Override
    public void testSuccessful(ExtensionContext context) {
        log.info("✓ PASSED: {}", context.getDisplayName());
        quitDriver();
    }

    @Override
    public void testFailed(ExtensionContext context, Throwable cause) {
        log.error("✗ FAILED: {}", context.getDisplayName());
        log.error("  Причина: {}", cause.getMessage());

        WebDriver driver = DRIVER.get();
        if (driver != null) {
            try {
                Path screenshot = ScreenshotUtils.takeScreenshot(driver, context.getDisplayName());
                log.error("  Скриншот: {}", screenshot.toAbsolutePath());
            } catch (Exception e) {
                log.warn("  Не удалось сделать скриншот: {}", e.getMessage());
            }
        } else {
            log.warn("  WebDriver недоступен — скриншот не сделан");
        }

        quitDriver();
    }

    @Override
    public void testAborted(ExtensionContext context, Throwable cause) {
        log.warn("⊘ ABORTED: {}", context.getDisplayName());
        quitDriver();
    }

    @Override
    public void testDisabled(ExtensionContext context, Optional<String> reason) {
        log.info("⊘ DISABLED: {} — {}", context.getDisplayName(),
                reason.orElse("без причины"));
    }

    private void quitDriver() {
        WebDriver driver = DRIVER.get();
        if (driver != null) {
            driver.quit();
            DRIVER.remove();
        }
    }
}