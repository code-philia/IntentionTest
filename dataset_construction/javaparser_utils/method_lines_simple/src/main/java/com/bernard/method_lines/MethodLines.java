package com.bernard.method_lines_simple;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;

import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;


import java.io.File;

/**
 * Some code that uses JavaParser.
 */
public class MethodLines {
    private static class MethodLineVisitor extends VoidVisitorAdapter {
        @Override
        public void visit(MethodDeclaration md, Object arg) {
            System.out.println(md.getName() + " " + md.getRange().get().begin.line + " " + md.getRange().get().end.line);
    
        }
    }
    public static void main(String[] args) {
        String path = args[0];

        File file = new File(path);
        try {
            CompilationUnit cu = StaticJavaParser.parse(file);
            new MethodLineVisitor().visit(cu, null);
        }
        catch (Exception e) {
            e.printStackTrace();
        }
        // CompilationUnit cu = StaticJavaParser.parse(file);
        // new MethodLineVisitor().visit(cu, null);
    }
}
