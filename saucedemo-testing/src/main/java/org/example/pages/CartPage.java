package org.example.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class CartPage extends BasePage {

    private static final By PAGE_TITLE = By.className("title");
    private static final By CHECKOUT_BUTTON = By.id("checkout");
    private static final By CONTINUE_SHOPPING_BUTTON = By.id("continue-shopping");

    public CartPage(WebDriver driver) {
        super(driver);
    }

    public String getPageTitle() {
        return getText(PAGE_TITLE);
    }

    public boolean isProductInCart(String productName) {
        By productLocator = By.xpath(
                String.format("//div[@class='inventory_item_name' and text()='%s']", productName));
        return !driver.findElements(productLocator).isEmpty();
    }

    public CheckoutPage goToCheckout() {
        click(CHECKOUT_BUTTON);
        return new CheckoutPage(driver);
    }

    public InventoryPage continueShopping() {
        click(CONTINUE_SHOPPING_BUTTON);
        return new InventoryPage(driver);
    }
}