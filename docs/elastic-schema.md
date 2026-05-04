https://ods-airport-data.kb.ap-south-1.aws.elastic-cloud.com:9243/app/enterprise_search/content/search_indices/search-master-hotel-details-test

properties/indexes in elastic using which we can query

```json
{
  "mappings": {
    "properties": {
      "address": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "brandName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "chainName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "checkInTime": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "checkOutTime": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "cityName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "countryCode": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "countryName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "hasImages": {
        "type": "boolean"
      },
      "hotelAvgRating": {
        "type": "float"
      },
      "hotelCode": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "hotelName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "hotelRating": {
        "type": "long"
      },
      "hotelTotalReviews": {
        "type": "long"
      },
      "houseRules": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "huserAvgRating": {
        "type": "float"
      },
      "location": {
        "type": "geo_point"
      },
      "pinCode": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "pricing": {
        "properties": {
          "currency": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "lastUpdated": {
            "type": "float"
          },
          "sampleCount": {
            "type": "long"
          },
          "source": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "version": {
            "type": "long"
          }
        }
      },
      "pricingV2": {
        "properties": {
          "currency": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "lastUpdated": {
            "type": "float"
          },
          "sampleCount": {
            "type": "long"
          },
          "source": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "version": {
            "type": "long"
          }
        }
      },
      "propertyType": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "providerCode": {
        "properties": {
          "CT": {
            "type": "keyword"
          },
          "TBO": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "TRAVCLAN": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "travclan": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          },
          "vervoTech": {
            "type": "text",
            "fields": {
              "keyword": {
                "type": "keyword",
                "ignore_above": 256
              }
            }
          }
        }
      },
      "rawFacilities": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "stateName": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "userAvgRating": {
        "type": "float"
      }
    }
  }
}
```

change this query based on what we need, using the properties/indexes in our elastic
```json
curl --location 'https://181f01242c7f41b1bbdaa71785ad1051.ap-south-1.aws.elastic-cloud.com:443/search-master-hotel-details-test/_search' \
--header 'Authorization: apiKey d1JjRnhJOEIxejVXWFF3RGFTUWk6NWFBM1lHSjhUZmFJRWtJSFJCWkhtdw==' \
--header 'Content-Type: application/json' \
--data '{
  "_source": true,  
  "query": {
    "bool": {
      "must_not": {
        "exists": {
          "field": "chainName"
        }
      }
    }
  },
  "from": 0,
  "size": 10000  
}'
```

## state / country / Area / locality search with bounding-box
curl --location 'https://181f01242c7f41b1bbdaa71785ad1051.ap-south-1.aws.elastic-cloud.com:443/search-master-hotel-details-test/_search' \
--header 'Authorization: apiKey d1JjRnhJOEIxejVXWFF3RGFTUWk6NWFBM1lHSjhUZmFJRWtJSFJCWkhtdw==' \
--header 'Content-Type: application/json' \
--data '{
    "query": {
        "bool": {
            "filter": [
                {
                    "geo_distance": {
                        "distance": "25.0km",
                        "location": {
                            "lat": 12.9716,
                            "lon": 77.5946
                        },
                        "validation_method": "IGNORE_MALFORMED",
                        "distance_type": "arc"
                    }
                },
                {
                    "geo_bounding_box": {
                        "location": {
                            "top_left": {
                                "lat": 13.1394,
                                "lon": 77.4609
                            },
                            "bottom_right": {
                                "lat": 12.8341,
                                "lon": 77.7848
                            }
                        },
                        "validation_method": "IGNORE_MALFORMED",
                        "ignore_unmapped": true
                    }
                },
                {
                    "range": {
                        "hotelRating": {
                            "gte": 3
                        }
                    }
                },
                {
                    "term": {
                        "hasImages": true
                    }
                },
                {
                    "bool": {
                        "must": [
                            {
                                "exists": {
                                    "field": "providerCode.vervoTech"
                                }
                            },
                            {
                                "bool": {
                                    "should": [
                                        {
                                            "exists": {
                                                "field": "providerCode.CT"
                                            }
                                        },
                                        {
                                            "exists": {
                                                "field": "providerCode.TBO"
                                            }
                                        }
                                    ],
                                    "minimum_should_match": 1
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
    "size": 20,
    "sort": [
        {
            "_geo_distance": {
                "location": {
                    "lat": 12.9716,
                    "lon": 77.5946
                },
                "order": "asc",
                "unit": "km",
                "distance_type": "arc",
                "ignore_unmapped": true
            }
        }
    ],
    "_source": [
        "hotelCode",
        "name",
        "address",
        "location",
        "hotelRating",
        "userRating",
        "userRatingCount",
        "thumbnailImage",
        "images",
        "amenities",
        "propertyType",
        "providerCode",
        "countryName",
        "stateName",
        "cityName"
    ],
    "timeout": "30s",
    "from": 0
}'