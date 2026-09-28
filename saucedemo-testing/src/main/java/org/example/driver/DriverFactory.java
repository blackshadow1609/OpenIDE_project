package org.example.driver;

import org.example.config.ConfigReader;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.edge.EdgeDriver;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;

public class DriverFactory {

    private static final Logger log = LoggerFactory.getLogger(DriverFactory.class);

    public static WebDriver createDriver() {
        String browser = ConfigReader.get("browser").toLowerCase();
        boolean headless = ConfigReader.getBoolean("headless");

        log.info("Создаю WebDriver: browser={}, headless={}", browser, headless);

        WebDriver driver;
        switch (browser) {
            case "chrome" -> {
                ChromeOptions options = new ChromeOptions();
                if (headless) {
                    options.addArguments("--headless=new");
                }
                options.addArguments("--disable-gpu", "--window-size=1920,1080");
                driver = new ChromeDriver(options);
            }
            case "firefox" -> driver = new FirefoxDriver();
            case "edge" -> driver = new EdgeDriver();
            default -> throw new IllegalArgumentException(
                    "Неизвестный браузер: " + browser + ". Поддерживаются: chrome, firefox, edge.");
        }

        driver.manage().window().maximize();
        driver.manage().timeouts()
                .implicitlyWait(Duration.ofSeconds(ConfigReader.getInt("implicit.wait")));

        return driver;
    }
}