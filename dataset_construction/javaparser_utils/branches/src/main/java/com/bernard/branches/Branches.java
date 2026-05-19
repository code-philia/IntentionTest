package com.bernard.branches;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.stmt.IfStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.visitor.ModifierVisitor;
import com.github.javaparser.ast.visitor.Visitable;
import com.github.javaparser.utils.CodeGenerationUtils;
import com.github.javaparser.utils.Log;
import com.github.javaparser.utils.SourceRoot;

import java.nio.file.Paths;
import java.io.File;

/**
 * Some code that uses JavaParser.
 */
public class Branches {
    private static class BranchesVisitor extends VoidVisitorAdapter {
        int i = 0;
        @Override
        public void visit(IfStmt is, Object arg) {
            
            i++;

            is.getThenStmt().accept(this, arg);
            if (is.getElseStmt().isPresent()) {
                is.getElseStmt().get().accept(this, arg);
            }

            System.out.println(is);
            System.out.println(i);
        }
    }

    public static void main(String[] args) {
        String path = args[0];
        try {
            File file = new File(path);
            CompilationUnit cu = StaticJavaParser.parse(file);
            new BranchesVisitor().visit(cu, null);
        }
        catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
    }
}
