#!/usr/bin/env python3

from mip_helper import io_helper
from mip_helper.shapes import Shapes

import logging
import json

from pandas import DataFrame
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

DESIGN_PARAM = "design"
DEFAULT_DESIGN = "factorial"

DEFAULT_DOCKER_IMAGE = "python-anova"


def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Read inputs
    inputs = io_helper.fetch_data()
    dep_var = inputs["data"]["dependent"][0]
    inped_vars = inputs["data"]["independent"]
    design = get_parameter(inputs["parameters"], DESIGN_PARAM)

    # Check dependent variable type (should be continuous)
    if dep_var["type"]["name"] not in ["integer", "real"]:
        logging.warning("Dependent variable should be continuous !")
        return None

    # Extract data and parameters from inputs
    data = format_data(inputs["data"])

    # Compute anova and generate PFA output
    anova_results = format_output(compute_anova(dep_var, inped_vars, data, design).to_dict())

    # Store results
    io_helper.save_results(anova_results, Shapes.JSON)


def format_data(input_data):
    all_vars = input_data["dependent"] + input_data["independent"]
    data = {v["name"]: v["series"] for v in all_vars}
    return data


def format_output(statsmodels_dict):
    return json.dumps(DataFrame.from_dict(statsmodels_dict).transpose().fillna("NaN").to_dict())


def get_parameter(params_list, param_name):
    for p in params_list:
        if p["name"] == param_name:
            return p["value"]
    return DEFAULT_DESIGN


def compute_anova(dep_var, indep_vars, data, design='factorial'):
    formula = generate_formula(dep_var, indep_vars, design)
    logging.info("Formula: %s" % formula)
    lm = ols(data=data, formula=formula).fit()
    logging.info(lm.summary())
    return anova_lm(lm)


def generate_formula(dep_var, indep_vars, design):
    if design == 'additive':
        op = " + "
    elif design == 'factorial':
        op = " * "
    else:
        logging.error("Invalid design parameter : %s" % design)
        return None
    dep_var = dep_var["name"]
    indep_vars = [v["name"] if v["type"]["name"] in ["integer", "real"]
                  else str.format("C(%s)" % v["name"]) for v in indep_vars]
    indep_vars = op.join(indep_vars)
    indep_vars = indep_vars.strip(op)
    return str.format("%s ~ %s" % (dep_var, indep_vars))


if __name__ == '__main__':
    main()
