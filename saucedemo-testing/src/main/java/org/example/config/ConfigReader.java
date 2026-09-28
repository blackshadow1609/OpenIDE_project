package org.example.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

public class ConfigReader {

    private static final Logger log = LoggerFactory.getLogger(ConfigReader.class);
    private static final Properties PROPERTIES = new Properties();

    static {
        try (InputStream input = ConfigReader.class
                .getClassLoader()
                .getResourceAsStream("config.properties")) {
            if (input == null) {
                throw new RuntimeException("Файл config.properties не найден в resources");
            }
            PROPERTIES.load(input);
            log.info("Конфигурация загружена: {} свойств", PROPERTIES.size());
        } catch (IOException e) {
            throw new RuntimeException("Ошибка при чтении config.properties", e);
        }
    }

    public static String get(String key) {
        String value = PROPERTIES.getProperty(key);
        if (value == null) {
            throw new RuntimeException("Свойство '" + key + "' не найдено в config.properties");
        }
        return value;
    }

    public static int getInt(String key) {
        return Integer.parseInt(get(key));
    }

    public static boolean getBoolean(String key) {
        return Boolean.parseBoolean(get(key));
    }
}