#!/usr/bin/env python3
# Copyright (C) 2017  LREN CHUV for Human Brain Project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mip_helper import io_helper, shapes, errors, utils

import argparse
import itertools
import logging
import json
import numpy as np
import pandas as pd
from tableschema import validate, exceptions


# Configure logging
logging.basicConfig(level=logging.INFO)


def _validate_schema(schema):
    try:
        validate(schema)
    except exceptions.ValidationError as exception:
        for error in exception.errors:
            raise error


# TODO: use something more fancy like schematics instead of dict?
OUTPUT_SCHEMA_INTERMEDIATE = {
    'fields': [
        {'name': 'group_variables', 'type': 'array'},
        {'name': 'group', 'type': 'array'},
        {'name': 'index', 'type': 'string'},
        {'name': 'label', 'type': 'string'},
        {'name': 'type', 'type': 'string'},
        {'name': 'count', 'type': 'integer'},
        {'name': 'null_count', 'type': 'integer'},
        {'name': 'unique', 'type': 'integer'},
        {'name': 'top', 'type': 'string'},
        {'name': 'frequency', 'type': 'any'},
        {'name': 'mean', 'type': 'number'},
        {'name': 'std', 'type': 'number'},
        {'name': 'EX^2', 'type': 'number'},
        {'name': 'min', 'type': 'number'},
        {'name': 'max', 'type': 'number'},
        {'name': '25%', 'type': 'number'},
        {'name': '50%', 'type': 'number'},
        {'name': '75%', 'type': 'number'},
    ]
}
_validate_schema(OUTPUT_SCHEMA_INTERMEDIATE)


# TODO: for distributed case calculate percentiles using Q-Digest or T-Digest algorithm
OUTPUT_SCHEMA_AGGREGATE = {
    'fields': [
        {'name': 'group_variables', 'type': 'array'},
        {'name': 'group', 'type': 'array'},
        {'name': 'index', 'type': 'string'},
        {'name': 'label', 'type': 'string'},
        {'name': 'type', 'type': 'string'},
        {'name': 'count', 'type': 'integer'},
        {'name': 'null_count', 'type': 'integer'},
        {'name': 'frequency', 'type': 'any'},
        {'name': 'mean', 'type': 'number'},
        {'name': 'std', 'type': 'number'},
        {'name': 'min', 'type': 'number'},
        {'name': 'max', 'type': 'number'}
    ]
}
_validate_schema(OUTPUT_SCHEMA_AGGREGATE)


@utils.catch_user_error
def intermediate_stats():
    """Calculate summary statistics for single node."""
    # Read inputs
    logging.info("Fetching data...")
    inputs = io_helper.fetch_data()
    dep_var = inputs["data"]["dependent"][0]
    indep_vars = inputs["data"]["independent"]
    labels = _get_labels(indep_vars + [dep_var])
    types = _get_types(indep_vars + [dep_var])

    if len(dep_var['series']) == 0:
        raise errors.UserError('Dependent variable has no values, check your SQL query.')

    # Load data into a Pandas dataframe
    logging.info("Loading data...")
    df = io_helper.fetch_dataframe(variables=[dep_var] + indep_vars)

    # Generate results
    logging.info("Generating results...")

    group_variables = [var['name'] for var in indep_vars if utils.is_nominal(var)]

    # grouped statistics
    data = []
    if group_variables:
        for group_name, group in df.groupby(group_variables):
            # if there's only one nominal column
            if not isinstance(group_name, tuple):
                group_name = (group_name,)

            data += _calc_stats(group, group_name, group_variables, labels, types)

    # overall statistics
    data += _calc_stats(df, ('all',), [], labels, types)

    logging.info("Results:\n{}".format(data))
    table = {
        'schema': OUTPUT_SCHEMA_INTERMEDIATE,
        'data': data,
    }
    io_helper.save_results(pd.io.json.dumps(table), shapes.Shapes.TABULAR_DATA_RESOURCE)
    logging.info("DONE")


def _calc_stats(group, group_name, group_variables, labels, types):
    results = []
    for name, x in group.items():
        result = {
            'index': name,
            'label': labels[name],
            'type': types[name],
            'group': list(map(str, group_name)),
            'group_variables': [labels[g] for g in group_variables],
        }

        # add all stats from pandas
        result.update(x.describe().drop('freq', errors='ignore'))

        if x.dtype.name == 'category':
            result['frequency'] = dict(x.value_counts())
        else:
            # add EX^2 for calculation of std in distributed scenario
            result['EX^2'] = np.mean(x**2)

        result['count'] = len(x)
        result['null_count'] = pd.isnull(x).sum()
        results.append(result)

    return results


@utils.catch_user_error
def aggregate_stats(job_ids):
    """Get all partial statistics from all nodes and aggregate them.
    :input job_ids: list of job_ids with intermediate results
    """
    # Read intermediate inputs from jobs
    logging.info("Fetching intermediate data...")
    df = _load_intermediate_data(job_ids)

    # Aggregate summary statistics
    logging.info("Aggregating results...")
    data = []
    for (group_name, index), gf in df.groupby(['group', 'index']):
        data.append(_agg_stats(gf, group_name, index))

    logging.info("Results:\n{}".format(data))
    table = {
        'schema': OUTPUT_SCHEMA_AGGREGATE,
        'data': data,
    }
    io_helper.save_results(pd.io.json.dumps(table), shapes.Shapes.TABULAR_DATA_RESOURCE)
    logging.info("DONE")


def _load_intermediate_data(job_ids):
    jobs_data = [io_helper.get_results(job_id).data for job_id in job_ids]
    # chain all results together, ignore empty results
    data = list(itertools.chain(*[json.loads(d)['data'] for d in jobs_data if d]))

    if not data:
        raise errors.UserError('Intermediate jobs {} do not have any data.'.format(job_ids))

    df = pd.DataFrame(data)
    df['group'] = df['group'].map(tuple)
    return df


def _agg_stats(gf, group_name, index):
    ret = {
        'index': index,
        'label': gf.label.iloc[0],
        'type': gf.type.iloc[0],
        'group': group_name,
        'group_variables': gf.group_variables.iloc[0],
        'count': gf['count'].sum(),
        'null_count': gf['null_count'].sum(),
    }
    # nominal
    if 'frequency' in gf.columns:
        total_freq = pd.DataFrame(list(gf.frequency)).sum()
        ret.update({'frequency': total_freq.to_dict()})

    # real variable
    else:
        mean = (gf['mean'] * gf['count']).sum() / gf['count'].sum()
        ret.update({
            'mean': mean,
            # std = EX^2 - (EX)^2
            'std': np.sqrt((gf['EX^2'] * gf['count']).sum() / gf['count'].sum() - mean**2),
            'min': gf['min'].min(),
            'max': gf['max'].max(),
        })
    return ret


def _get_labels(variables):
    return {var['name']: var.get('label', var['name']) for var in variables}


def _get_types(variables):
    return {var['name']: var.get('type', {}).get('name') for var in variables}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('compute', choices=['compute'])
    parser.add_argument('--mode', choices=['intermediate', 'aggregate'], default='intermediate')
    # QUESTION: (job_id, node) is a primary key of `job_result` table. Does it mean I'll need node ids as well in order
    # to query unique job?
    parser.add_argument('--job-ids', type=str, nargs="*", default=[])

    args = parser.parse_args()

    # > compute --mode intermediate
    if args.mode == 'intermediate':
        intermediate_stats()
    # > compute --mode aggregate --job-ids 12 13 14
    elif args.mode == 'aggregate':
        aggregate_stats(args.job_ids)
