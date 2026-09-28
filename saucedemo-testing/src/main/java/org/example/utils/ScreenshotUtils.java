package org.example.utils;

import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public final class ScreenshotUtils {

    private static final Logger log = LoggerFactory.getLogger(ScreenshotUtils.class);
    private static final Path SCREENSHOT_DIR = Paths.get("target", "screenshots");
    private static final DateTimeFormatter TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss-SSS");

    private ScreenshotUtils() { }

    public static Path takeScreenshot(WebDriver driver, String testName) {
        if (driver == null) {
            throw new IllegalArgumentException("driver не должен быть null");
        }

        try {
            Files.createDirectories(SCREENSHOT_DIR);

            byte[] screenshotBytes = ((TakesScreenshot) driver)
                    .getScreenshotAs(OutputType.BYTES);

            String safeName = testName.replaceAll("[^a-zA-Z0-9-_]", "_");
            String fileName = safeName + "_" + LocalDateTime.now().format(TIMESTAMP) + ".png";
            Path destination = SCREENSHOT_DIR.resolve(fileName);

            Files.write(destination, screenshotBytes);
            log.debug("Скриншот сохранён: {}", destination.toAbsolutePath());
            return destination;
        } catch (IOException e) {
            throw new RuntimeException("Не удалось сохранить скриншот", e);
        }
    }
}