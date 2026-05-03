"""Unit tests for PostgreSQL → Trino/Iceberg type mapping."""

import pytest

from src.transpiler.type_map import map_pg_type


class TestExactMappings:
    def test_serial_to_integer(self):
        assert map_pg_type("serial") == "INTEGER"

    def test_bigserial_to_bigint(self):
        assert map_pg_type("bigserial") == "BIGINT"

    def test_text_to_varchar(self):
        assert map_pg_type("text") == "VARCHAR"

    def test_bytea_to_varbinary(self):
        assert map_pg_type("bytea") == "VARBINARY"

    def test_jsonb_to_varchar(self):
        assert map_pg_type("jsonb") == "VARCHAR"

    def test_json_to_varchar(self):
        assert map_pg_type("json") == "VARCHAR"

    def test_uuid_preserved(self):
        assert map_pg_type("uuid") == "UUID"

    def test_timestamptz(self):
        assert map_pg_type("timestamptz") == "TIMESTAMP(6) WITH TIME ZONE"

    def test_timestamp_with_tz(self):
        assert map_pg_type("timestamp with time zone") == "TIMESTAMP(6) WITH TIME ZONE"

    def test_timestamp_without_tz(self):
        assert map_pg_type("timestamp without time zone") == "TIMESTAMP(6)"

    def test_boolean(self):
        assert map_pg_type("boolean") == "BOOLEAN"

    def test_bool(self):
        assert map_pg_type("bool") == "BOOLEAN"

    def test_date(self):
        assert map_pg_type("date") == "DATE"

    def test_double_precision(self):
        assert map_pg_type("double precision") == "DOUBLE"

    def test_real(self):
        assert map_pg_type("real") == "REAL"

    def test_money(self):
        assert map_pg_type("money") == "DECIMAL(19,4)"

    def test_interval_to_varchar(self):
        assert map_pg_type("interval") == "VARCHAR"


class TestParameterisedTypes:
    def test_varchar_n(self):
        assert map_pg_type("varchar(255)") == "VARCHAR(255)"

    def test_character_varying_n(self):
        assert map_pg_type("character varying(100)") == "VARCHAR(100)"

    def test_char_n(self):
        assert map_pg_type("char(2)") == "CHAR(2)"

    def test_character_n(self):
        assert map_pg_type("character(10)") == "CHAR(10)"

    def test_numeric_p_s(self):
        assert map_pg_type("numeric(10,2)") == "DECIMAL(10,2)"

    def test_decimal_p_s(self):
        assert map_pg_type("decimal(12,4)") == "DECIMAL(12,4)"

    def test_numeric_p_only(self):
        assert map_pg_type("numeric(18)") == "DECIMAL(18,0)"

    def test_numeric_no_params(self):
        assert map_pg_type("numeric") == "DECIMAL(38,9)"

    def test_decimal_no_params(self):
        assert map_pg_type("decimal") == "DECIMAL(38,9)"

    def test_timestamp_n(self):
        assert map_pg_type("timestamp(3)") == "TIMESTAMP(3)"

    def test_timestamp_n_with_tz(self):
        assert map_pg_type("timestamp(6) with time zone") == "TIMESTAMP(6) WITH TIME ZONE"


class TestIntegerAliases:
    def test_int2(self):
        assert map_pg_type("int2") == "SMALLINT"

    def test_int4(self):
        assert map_pg_type("int4") == "INTEGER"

    def test_int8(self):
        assert map_pg_type("int8") == "BIGINT"

    def test_integer(self):
        assert map_pg_type("integer") == "INTEGER"

    def test_bigint(self):
        assert map_pg_type("bigint") == "BIGINT"

    def test_smallint(self):
        assert map_pg_type("smallint") == "SMALLINT"


class TestArrayTypes:
    def test_integer_array(self):
        assert map_pg_type("integer[]") == "ARRAY(INTEGER)"

    def test_text_array(self):
        assert map_pg_type("text[]") == "ARRAY(VARCHAR)"

    def test_varchar_array(self):
        result = map_pg_type("varchar(50)[]")
        assert result == "ARRAY(VARCHAR(50))"


class TestCaseInsensitivity:
    def test_uppercase_input(self):
        assert map_pg_type("TEXT") == "VARCHAR"

    def test_mixed_case_input(self):
        assert map_pg_type("Numeric(10,2)") == "DECIMAL(10,2)"

    def test_uppercase_timestamptz(self):
        assert map_pg_type("TIMESTAMPTZ") == "TIMESTAMP(6) WITH TIME ZONE"
