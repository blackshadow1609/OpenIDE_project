package org.example.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.Select;

import java.util.List;
import java.util.stream.Collectors;

public class InventoryPage extends BasePage {

    private static final By SORT_DROPDOWN = By.className("product_sort_container");
    private static final By CART_BADGE = By.className("shopping_cart_badge");
    private static final By CART_ICON = By.className("shopping_cart_link");
    private static final By PRODUCT_NAMES = By.className("inventory_item_name");

    public InventoryPage(WebDriver driver) {
        super(driver);
    }

    public String getPageTitle() {
        return getText(By.className("title"));
    }

    public InventoryPage sortBy(String visibleText) {
        Select select = new Select(waitForVisible(SORT_DROPDOWN));
        select.selectByVisibleText(visibleText);
        return this;
    }

    public List<String> getProductNames() {
        return driver.findElements(PRODUCT_NAMES).stream()
                .map(WebElement::getText)
                .collect(Collectors.toList());
    }

    public InventoryPage addToCart(String productName) {
        String xpath = String.format(
                "//div[text()='%s']/ancestor::div[@class='inventory_item']//button",
                productName);
        click(By.xpath(xpath));
        return this;
    }

    public String getCartBadgeCount() {
        return getText(CART_BADGE);
    }

    public CartPage goToCart() {
        click(CART_ICON);
        return new CartPage(driver);
    }
}