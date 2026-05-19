def load_konwledge(example_id):
    # Load the domain knowledge for the given example_id
    if example_id == 1:
        return load_knowledge_example_1()
    elif example_id == 4:
        return load_knowledge_example_4()
    else:
        raise ValueError("Invalid example_id")
    

def load_knowledge_example_1():
    method_body = {
        "create(100, 10, 10000)": """public Server create(int maxThreads, int minThreads, int threadTimeoutMillis) {\n    Server server;\n\n    if (maxThreads > 0) {\n        int max = maxThreads;\n        int min = (minThreads > 0) ? minThreads : 8;\n        int idleTimeout = (threadTimeoutMillis > 0) ? threadTimeoutMillis : 60000;\n\n        server = new Server(new QueuedThreadPool(max, min, idleTimeout));\n    } else {\n        server = new Server();\n    }\n\n    return server;\n}""",

        "create(routes, staticFilesConfiguration, exceptionMapper, false)": """public EmbeddedServer create(Routes routeMatcher,\n                                StaticFilesConfiguration staticFilesConfiguration,\n                                ExceptionMapper exceptionMapper,\n                                boolean hasMultipleHandler) {\n    MatcherFilter matcherFilter = new MatcherFilter(routeMatcher, staticFilesConfiguration, exceptionMapper, false, hasMultipleHandler);\n    matcherFilter.init(null);\n\n    JettyHandler handler = new JettyHandler(matcherFilter);\n    handler.getSessionCookieConfig().setHttpOnly(httpOnly);\n    return new EmbeddedJettyServer(serverFactory, handler).withThreadPool(threadPool);\n}""",

        "extinguish()": """public void extinguish() {\n    logger.info(">>> {} shutting down ...", NAME);\n    try {\n        if (server != null) {\n            server.stop();\n        }\n    } catch (Exception e) {\n        logger.error("stop failed", e);\n        System.exit(100); // NOSONAR\n    }\n    logger.info("done");\n}""",

        """ignite("localhost", 6759, null, 100, 10, 10000)""": """public int ignite(String host,\n                    int port,\n                    SslStores sslStores,\n                    int maxThreads,\n                    int minThreads,\n                    int threadIdleTimeoutMillis) throws Exception {\n\n    boolean hasCustomizedConnectors = false;\n\n    if (port == 0) {\n        try (ServerSocket s = new ServerSocket(0)) {\n            port = s.getLocalPort();\n        } catch (IOException e) {\n            logger.error("Could not get first available port (port set to 0), using default: {}", SPARK_DEFAULT_PORT);\n            port = SPARK_DEFAULT_PORT;\n        }\n    }\n\n    // Create instance of jetty server with either default or supplied queued thread pool\n    if(threadPool == null) {\n        server = serverFactory.create(maxThreads, minThreads, threadIdleTimeoutMillis);\n    } else {\n        server = serverFactory.create(threadPool);\n    }\n\n    ServerConnector connector;\n\n    if (sslStores == null) {\n        connector = SocketConnectorFactory.createSocketConnector(server, host, port, trustForwardHeaders);\n    } else {\n        connector = SocketConnectorFactory.createSecureSocketConnector(server, host, port, sslStores, trustForwardHeaders);\n    }\n\n    Connector previousConnectors[] = server.getConnectors();\n    server = connector.getServer();\n    if (previousConnectors.length != 0) {\n        server.setConnectors(previousConnectors);\n        hasCustomizedConnectors = true;\n    } else {\n        server.setConnectors(new Connector[] {connector});\n    }\n\n    ServletContextHandler webSocketServletContextHandler =\n        WebSocketServletContextHandlerFactory.create(webSocketHandlers, webSocketIdleTimeoutMillis);\n\n    // Handle web socket routes\n    if (webSocketServletContextHandler == null) {\n        server.setHandler(handler);\n    } else {\n        List<Handler> handlersInList = new ArrayList<>();\n        handlersInList.add(handler);\n\n        // WebSocket handler must be the last one\n        if (webSocketServletContextHandler != null) {\n            handlersInList.add(webSocketServletContextHandler);\n        }\n\n        HandlerList handlers = new HandlerList();\n        handlers.setHandlers(handlersInList.toArray(new Handler[handlersInList.size()]));\n        server.setHandler(handlers);\n    }\n\n    logger.info("== {} has ignited ...", NAME);\n    if (hasCustomizedConnectors) {\n        logger.info(">> Listening on Custom Server ports!");\n    } else {\n        logger.info(">> Listening on {}:{}", host, port);\n    }\n\n    server.start();\n    return port;\n}""",
        "trustForwardHeaders(true)": """public void trustForwardHeaders(boolean trust) {\n    this.trustForwardHeaders = trust;\n}""",

        """withThreadPool(null)""": """public EmbeddedJettyFactory withThreadPool(ThreadPool threadPool) {\n    this.threadPool = threadPool;\n    return this;\n}""",

        """Server()""": """public Server()\n{\n    this((ThreadPool)null);\n}"""
    }

    overloaded_signatures = {
        "create(100, 10, 10000)": ["Server create(ThreadPool threadPool)"],

        "QueuedThreadPool()": ["QueuedThreadPool(int maxThreads)",
                               "QueuedThreadPool(int maxThreads, int minThreads)",
                               "QueuedThreadPool(int maxThreads, int minThreads, int idleTimeout)",
                               "QueuedThreadPool(int maxThreads, int minThreads, int idleTimeout, int reservedThreads, BlockingQueue<Runnable> queue, ThreadGroup threadGroup)",
                               "QueuedThreadPool(int maxThreads, int minThreads, int idleTimeout, int reservedThreads, BlockingQueue<Runnable> queue, ThreadGroup threadGroup, ThreadFactory threadFactory)",
                               "QueuedThreadPool(int maxThreads, int minThreads, int idleTimeout, BlockingQueue<Runnable> queue)",
                               "QueuedThreadPool(int maxThreads, int minThreads, int idleTimeout, BlockingQueue<Runnable> queue, ThreadGroup threadGroup)",
                               "QueuedThreadPool(int maxThreads, int minThreads, BlockingQueue<Runnable> queue)"],

        "EmbeddedJettyFactory(jettyServerFactory)": ["""public EmbeddedJettyFactory withThreadPool(ThreadPool threadPool) {\n    this.threadPool = threadPool;\n    return this;\n}"""],

        "EmbeddedJettyFactory(jettyServerFactory)": ["""EmbeddedJettyFactory()"""],

        """Server()""": ["Server(int port)",
                         "Server(java.net.InetSocketAddress addr)",
                         "Server(ThreadPool pool)"]

    }

    return {
        "method_body": method_body,
        "overloaded_signatures": overloaded_signatures
    }

def load_knowledge_example_4():
    method_body = {
        # "WeekDay": """// NOTE: Constant MONDAY does not exists in WeekDay\npublic class WeekDay implements Serializable {\n\n    private static final long serialVersionUID = -1542525283511798919L;\n    private final int mondayDoWValue;\n    private final boolean firstDayZero;\n\n    public WeekDay(final int mondayDoWValue, final boolean firstDayZero) {\n        Preconditions.checkArgument(mondayDoWValue >= 0, "Monday Day of Week value must be greater or equal to zero");\n        this.mondayDoWValue = mondayDoWValue;\n        this.firstDayZero = firstDayZero;\n    }\n}""",
        "WeekDay": """public class WeekDay implements Serializable {\n\n    private static final long serialVersionUID = -1542525283511798919L;\n    private final int mondayDoWValue;\n    private final boolean firstDayZero;\n\n    public WeekDay(final int mondayDoWValue, final boolean firstDayZero);\n\n    public int getMondayDoWValue();\n\n    public boolean isFirstDayZero();\n\n    public int mapTo(final int dayOfWeek, final WeekDay targetWeekDayDefinition);\n\n    private Function<Integer, Integer> bothSameStartOfRange(final int startRange, final int endRange, final WeekDay source, final WeekDay target);\n}""",
        "CronFieldName": """public enum CronFieldName {\n    SECOND(0), MINUTE(1), HOUR(2), DAY_OF_MONTH(3), MONTH(4), DAY_OF_WEEK(5), YEAR(6), DAY_OF_YEAR(7);\n    private int order;\n\n    CronFieldName(final int order);\n\n    public int getOrder();\n}"""
    }
    overloaded_signatures = {}

    # extended_class_constructor_body = {
    #     "EveryDayOfWeekValueGenerator": """public EveryFieldValueGenerator(final CronField cronField) {\n    super(cronField);\n\n    final Every every = (Every) cronField.getExpression();\n    final FieldExpression everyExpression = every.getExpression();\n    if (everyExpression instanceof Between) {\n        final Between between = (Between) everyExpression;\n\n        from = Math.max(cronField.getConstraints().getStartRange(), BetweenFieldValueGenerator.map(between.getFrom()));\n        to = Math.min(cronField.getConstraints().getEndRange(), BetweenFieldValueGenerator.map(between.getTo()));\n    } else if(everyExpression instanceof On){\n\n        final On on = (On) everyExpression;\n\n        from = on.getTime().getValue();\n        to = cronField.getConstraints().getEndRange();\n    } else {\n        from = cronField.getConstraints().getStartRange();\n        to = cronField.getConstraints().getEndRange();\n    }\n}""",

    #     "EveryFieldValueGenerator": """public FieldValueGenerator(final CronField cronField) {\n    this.cronField = Preconditions.checkNotNull(cronField, "CronField must not be null");\n    Preconditions.checkArgument(matchesFieldExpressionClass(cronField.getExpression()), "FieldExpression does not match required class");\n}"""
    # }

    # override_method_body = {
    #     "matchesFieldExpressionClass": {
    #         "EveryFieldValueGenerator": """protected boolean matchesFieldExpressionClass(final FieldExpression fieldExpression) {\n    return fieldExpression instanceof Every;\n}""",

    #         "OnFieldValueGenerator": """protected boolean matchesFieldExpressionClass(final FieldExpression fieldExpression) {\n    return fieldExpression instanceof On;\n}""",

    #         # omitted 9 more overrides
    #     }
    # }

    parameters = {}

    additional_knowledge = {
        "EveryDayOfWeekValueGenerator": [
            (
                "The method body of `matchesFieldExpressionClass`, which is invoked by the constructor `EveryDayOfWeekValueGenerator()`", 
                "protected boolean matchesFieldExpressionClass(final FieldExpression fieldExpression) {\n    return fieldExpression instanceof Every;\n}"
            ),
            (
                "The parameter information of the constructor `EveryDayOfWeekValueGenerator`", 
                """public class WeekDay implements Serializable {\n\n    private static final long serialVersionUID = -1542525283511798919L;\n    private final int mondayDoWValue;\n    private final boolean firstDayZero;\n\n    public WeekDay(final int mondayDoWValue, final boolean firstDayZero);\n\n    public int getMondayDoWValue();\n\n    public boolean isFirstDayZero();\n\n    public int mapTo(final int dayOfWeek, final WeekDay targetWeekDayDefinition);\n\n    private Function<Integer, Integer> bothSameStartOfRange(final int startRange, final int endRange, final WeekDay source, final WeekDay target);\n}"""
            )
        ],
        "Every": [
            (
                "The bodies of available constructor `Every()` and the usage example of constructor `Every`",
                """public Every(final IntegerFieldValue time) {\n    this(always(), time);\n}\n```\n\n\n```\npublic Every(final FieldExpression expression, final IntegerFieldValue period) {\n    this.expression = Preconditions.checkNotNull(expression, "Expression must not be null");\n    this.period = period == null ? new IntegerFieldValue(1) : period;\n}\n```\n\n\nA Usage Example for Every\n```\nnew Every(new Between(map(array[0]), map(every[0])), mapToIntegerFieldValue(every[1]));"""
            )
        ],
        "CronField": [
            (
                "The parameter information of the constructor `public CronField(final CronFieldName field, final FieldExpression expression, final FieldConstraints constraints)`.",
                """FieldExpression is an abstract class that has several subclasses. The following constructors are the constructors of these subclasses:\n\nprivate Always()\npublic And()\npublic Between(final Between between)\npublic Between(final FieldValue<?> from, final FieldValue<?> to)\npublic Every(final IntegerFieldValue time)\npublic Every(final FieldExpression expression, final IntegerFieldValue period)\npublic On(final SpecialCharFieldValue specialChar)\npublic On(final IntegerFieldValue time)\npublic On(final IntegerFieldValue time, final SpecialCharFieldValue specialChar)\npublic On(final IntegerFieldValue time, final SpecialCharFieldValue specialChar, final IntegerFieldValue nth)\nprivate QuestionMark()\n"""
            )
        ]
    }

    return {
        "method_body": method_body,
        "overloaded_signatures": overloaded_signatures,
        "additional_knowledge": additional_knowledge,
    }