from pyspark.sql import SparkSession
import time

def main() -> None:
    spark = (
        SparkSession.builder
        .appName("css439")
        .master("local[*]")
        .getOrCreate()
    )
    
    df = spark.range(0, 50000000)
    total_rows = df.count()
    df.show(100, truncate=False)

    with open(DD_JSON_PATH, "w", encoding="utf-8") as file:
        file.write('{"id":1,"name":"muslima"}\n')
        file.write("BAD LINE\n")

    df_json = (
        spark.read
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .json(DD_JSON_PATH)
    )
    df_json.filter(F.col("_corrupt_record").isNull()).show(truncate=False)

    hot = spark.range(1_000_000).select(F.lit("hot").alias("key"))
    cold = (
        spark.range(100)
        .withColumn("key", F.concat(F.lit("cold_"), F.col("id")))
        .select("key")
        .crossJoin(spark.range(10).select(F.lit(1).alias("rep")))
        .select("key")
    )
    skewed = hot.unionByName(cold)

    skewed.groupBy("key").count().orderBy(F.desc("count")).show(20, truncate=False)
    
    time.sleep(120)
    spark.stop()


if __name__ == "__main__":
    main()

