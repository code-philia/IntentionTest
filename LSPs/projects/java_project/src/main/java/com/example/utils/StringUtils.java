package com.example.utils;

public class StringUtils {
    // 反转字符串
    public static String reverse(String input) {
        if (input == null) {
            return "";
        }
        return new StringBuilder(input).reverse().toString();
    }
}
