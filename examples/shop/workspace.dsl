workspace "Shop (example)" "Small example system for trying out the architecture-as-code workflow." {

    !identifiers hierarchical

    model {
        customer = person "Customer" "Buys products online."

        shop = softwareSystem "Shop" "Lets customers browse and order products." {
            web = container "Web Frontend" "Serves the shop UI." "TypeScript, Next.js" "Web"
            api = container "Order API" "Accepts and tracks orders." "Python, FastAPI"
            worker = container "Fulfilment Worker" "Consumes order events and ships orders." "Python"
            db = container "Order Database" "Stores orders." "PostgreSQL" "Database"
            events = container "Order Events" "Order lifecycle events." "Kafka topic" "Queue"
        }

        payments = softwareSystem "Payment Provider" "External card payments." "External"

        customer -> shop.web "Browses and orders using" "HTTPS"
        shop.web -> shop.api "Places orders via" "JSON/HTTPS"
        shop.api -> shop.db "Reads and writes" "SQL"
        shop.api -> shop.events "Publishes OrderPlaced to" "Kafka"
        shop.worker -> shop.events "Consumes OrderPlaced from" "Kafka"
        shop.api -> payments "Charges cards via" "HTTPS"

        # Deployment: the kubernetes.* properties are the contract the drift check reads.
        # See docs/conventions.md before adding or renaming one.
        local = deploymentEnvironment "local-kind" {
            deploymentNode "kind cluster" "Local Kubernetes in containers." "kind" {
                deploymentNode "shop" "" "Kubernetes Namespace" {
                    properties {
                        "kubernetes.namespace" "shop"
                    }
                    containerInstance shop.web {
                        properties {
                            "kubernetes.kind" "Deployment"
                            "kubernetes.name" "shop-web"
                        }
                    }
                    containerInstance shop.api {
                        properties {
                            "kubernetes.kind" "Deployment"
                            "kubernetes.name" "shop-api"
                        }
                    }
                    containerInstance shop.worker {
                        properties {
                            "kubernetes.kind" "Deployment"
                            "kubernetes.name" "shop-worker"
                        }
                    }
                    containerInstance shop.db {
                        properties {
                            "kubernetes.kind" "StatefulSet"
                            "kubernetes.name" "shop-db"
                        }
                    }
                }
            }
        }
    }

    views {
        systemContext shop "SystemContext" {
            include *
            autolayout lr
        }

        container shop "Containers" {
            include *
            autolayout lr
        }

        deployment shop local "LocalDeployment" {
            include *
            autolayout lr
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                shape person
                background #08427b
            }
            element "Software System" {
                background #1168bd
            }
            element "External" {
                background #999999
            }
            element "Container" {
                background #438dd5
            }
            element "Database" {
                shape cylinder
            }
            element "Queue" {
                shape pipe
            }
            element "Web" {
                shape webbrowser
            }
        }
    }
}
