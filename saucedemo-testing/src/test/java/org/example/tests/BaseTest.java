package org.example.tests;

import org.example.driver.DriverFactory;
import org.example.utils.ScreenshotOnFailureExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.WebDriver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@ExtendWith(ScreenshotOnFailureExtension.class)
public abstract class BaseTest {

    protected static final Logger log = LoggerFactory.getLogger(BaseTest.class);

    protected WebDriver driver;

    @BeforeEach
    void setUp(TestInfo testInfo) {
        driver = DriverFactory.createDriver();
        ScreenshotOnFailureExtension.setDriver(driver);
        log.info(">>> СТАРТ: {}", testInfo.getDisplayName());
    }
}