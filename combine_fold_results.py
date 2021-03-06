#!/usr/bin/env python

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import glob, re, argparse, sys, os
import sklearn.metrics


def read_results_file(file):
    '''Read columns of float data from a file, ignoring # comments'''
    rows = []
    with open(file, 'r') as f:
        for line in f:
            line = line.split('#', 1)[0].strip()
            if line:
                rows.append(map(float, line.split(' ')))
    return zip(*rows)


def write_results_file(file, *columns, **kwargs):
    '''Write columns of data to a file, with optional footer comment'''
    footer = kwargs.get('footer', '')
    with open(file, 'w') as f:
        for row in zip(*columns):
            f.write(' '.join(map(str, row)) + '\n')
        if footer:
            f.write('# %s' % footer)


def last_iters_statistics(test_aucs, test_interval, last_iters):
    n_last_tests = int(last_iters/test_interval)
    last_test_aucs = [x[-n_last_tests:] for x in test_aucs]
    return np.mean(last_test_aucs), np.max(last_test_aucs), np.min(last_test_aucs)


def training_plot(plot_file, train_series, test_series):
    assert len(train_series) == len(test_series)
    fig = plt.figure()
    plt.plot(train_series, label='Train')
    plt.plot(test_series, label='Test')
    plt.legend(loc='best')
    plt.savefig(plot_file, bbox_inches='tight')


def plot_roc_curve(plot_file, fpr, tpr, auc, txt):
    assert len(fpr) == len(tpr)
    fig = plt.figure(figsize=(8,8))
    plt.plot(fpr, tpr, label='CNN (AUC=%.2f)' % auc, linewidth=4)
    plt.legend(loc='lower right',fontsize=20)
    plt.xlabel('False Positive Rate',fontsize=22)
    plt.ylabel('True Positive Rate',fontsize=22)
    plt.axes().set_aspect('equal')
    plt.tick_params(axis='both', which='major', labelsize=16)
    plt.text(.05, -.25, txt, fontsize=22)
    plt.savefig(plot_file, bbox_inches='tight')


def plot_correlation(plot_file, y_aff, y_predaff, rmsd, r2):
    assert len(y_aff) == len(y_predaff)
    fig = plt.figure(figsize=(8,8))
    plt.plot(y_aff, y_predaff, 'o', label='RMSD=%.2f, R^2=%.3f (Pos)' % (rmsd, r2))
    plt.legend(loc='best', fontsize=20, numpoints=1)
    lo = np.min([np.min(y_aff), np.min(y_predaff)])
    hi = np.max([np.max(y_aff), np.max(y_predaff)])
    plt.xlim(lo, hi)
    plt.ylim(lo, hi)
    plt.xlabel('Experimental Affinity', fontsize=22)
    plt.ylabel('Predicted Affinity', fontsize=22)
    plt.axes().set_aspect('equal')
    plt.savefig(plot_file, bbox_inches='tight')


def check_file_exists(file):
    if not os.path.isfile(file):
        raise OSError('%s does not exist' % file)


def get_results_files(prefix, foldnums, binary_class, affinity, two_data_sources):
    files = {}
    if foldnums is None:
        foldnums = set()
        pattern = r'%s\.(\d+)\.(out|(auc|rmsd)\.final(test|train)2?)$' % prefix
        for file in glob.glob(prefix + '*'):
            match = re.match(pattern, file)
            if match:
                foldnums.add(int(match.group(1)))
    elif isinstance(foldnums, str):
        foldnums = [int(i) for i in foldnums.split(',') if i]
    for i in foldnums:
        files[i] = {}
        files[i]['out'] = '%s.%d.out' % (prefix, i)
        if binary_class:
            files[i]['auc_finaltest'] = '%s.%d.auc.finaltest' % (prefix, i)
            files[i]['auc_finaltrain'] = '%s.%d.auc.finaltrain' % (prefix, i)
        if affinity:
            files[i]['rmsd_finaltest'] = '%s.%d.rmsd.finaltest' % (prefix, i)
            files[i]['rmsd_finaltrain'] = '%s.%d.rmsd.finaltrain' % (prefix, i)
        if two_data_sources:
            if binary_class:
                files[i]['auc_finaltest2'] = '%s.%d.auc.finaltest2' % (prefix, i)
                files[i]['auc_finaltrain2'] = '%s.%d.auc.finaltrain2' % (prefix, i)
            if affinity:
                files[i]['rmsd_finaltest2'] = '%s.%d.rmsd.finaltest2' % (prefix, i)
                files[i]['rmsd_finaltrain2'] = '%s.%d.rmsd.finaltrain2' % (prefix, i)
    for i in files:
        for file in files[i].values():
            check_file_exists(file)
    return files


def filter_actives(values, y_true):
    return np.array(values)[np.array(y_true, dtype=np.bool)]


def combine_fold_results(test_metrics, train_metrics, test_labels, test_preds, train_labels, train_preds,
                         outprefix, test_interval, affinity=False, second_data_source=False,
                         filter_actives_test=None, filter_actives_train=None):
    '''Make results files and graphs combined from results for
    separate crossvalidation folds. test_metrics and train_metrics
    are lists of lists of AUCs or RMSDs for each fold, for each
    test_interval. test_labels and test_preds are labels and final
    test predictions for each test fold, in a single list. train_labels
    and train_preds are labels and predictions for each train fold in
    a single list. affinity says whether to interpret the labels and
    predictions as affinities, and the metric as RMSD instead of AUC.
    second_data_source sets the output file names to reflect whether
    the results are for the second data source of a combined data model.'''

    metric = 'rmsd' if affinity else 'auc'
    two = '2' if second_data_source else ''

    #average metric across folds
    mean_test_metrics = np.mean(test_metrics, axis=0)
    mean_train_metrics = np.mean(train_metrics, axis=0)

    #write test and train metrics (mean and for each fold)
    write_results_file('%s.%s.test%s' % (outprefix, metric, two), mean_test_metrics, *test_metrics)
    write_results_file('%s.%s.train%s' % (outprefix, metric, two), mean_train_metrics, *train_metrics)

    #training plot of mean test and train metric across folds
    training_plot('%s_%s_train%s.pdf' % (outprefix, metric, two), mean_train_metrics, mean_test_metrics)

    if affinity:

        if filter_actives_test:
            test_preds = filter_actives(test_preds, filter_actives_test)
            test_labels = filter_actives(test_labels, filter_actives_test)

        #correlation plots for last test iteration
        rmsd = np.sqrt(sklearn.metrics.mean_squared_error(test_preds, test_labels))
        r2 = sklearn.metrics.r2_score(test_preds, test_labels)
        write_results_file('%s.rmsd.finaltest%s' % (outprefix, two), test_preds, test_labels, footer='RMSD,R^2 %f %f\n' % (rmsd, r2))
        plot_correlation('%s_corr_test%s.pdf' % (outprefix, two), test_preds, test_labels, rmsd, r2)

        if filter_actives_train:
            train_preds = filter_actives(train_preds, filter_actives_train)
            train_labels = filter_actives(train_labels, filter_actives_train)

        rmsd = np.sqrt(sklearn.metrics.mean_squared_error(train_preds, train_labels))
        r2 = sklearn.metrics.r2_score(train_preds, train_labels)
        write_results_file('%s.rmsd.finaltrain%s' % (outprefix, two), train_preds, train_labels, footer='RMSD,R^2 %f %f\n' % (rmsd, r2))
        plot_correlation('%s_corr_train%s.pdf' % (outprefix, two), train_preds, train_labels, rmsd, r2)

    else:

        #roc curves for the last test iteration
        if len(np.unique(test_labels)) > 1:
            last_iters = 1000
            avg_auc, max_auc, min_auc = last_iters_statistics(test_metrics, test_interval, last_iters)
            txt = 'For the last %s iterations:\nmean AUC=%.2f  max AUC=%.2f  min AUC=%.2f' % (last_iters, avg_auc, max_auc, min_auc)
            fpr, tpr, _ = sklearn.metrics.roc_curve(test_labels, test_preds)
            auc = sklearn.metrics.roc_auc_score(test_labels, test_preds)
            write_results_file('%s.auc.finaltest%s' % (outprefix, two), test_labels, test_preds, footer='AUC %f\n' % auc)
            plot_roc_curve('%s_roc_test%s.pdf' % (outprefix, two), fpr, tpr, auc, txt)

        if len(np.unique(train_labels)) > 1:
            last_iters = 1000
            avg_auc, max_auc, min_auc = last_iters_statistics(train_metrics, test_interval, last_iters)
            txt = 'For the last %s iterations:\nmean AUC=%.2f  max AUC=%.2f  min AUC=%.2f' % (last_iters, avg_auc, max_auc, min_auc)
            fpr, tpr, _ = sklearn.metrics.roc_curve(train_labels, train_preds)
            auc = sklearn.metrics.roc_auc_score(train_labels, train_preds)
            write_results_file('%s.auc.finaltrain%s' % (outprefix, two), train_labels, train_preds, footer='AUC %f\n' % auc)
            plot_roc_curve('%s_roc_train%s.pdf' % (outprefix, two), fpr, tpr, auc, txt)



def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Combine training results from different folds and make graphs')
    parser.add_argument('-o','--outprefix',type=str,required=True,help="Prefix for input and output files (--outprefix from train.py)")
    parser.add_argument('-n','--foldnums',type=str,required=False,help="Fold numbers to combine, default is to determine using glob",default=None)
    parser.add_argument('-a','--affinity',default=False,action='store_true',required=False,help="Also look for affinity results files")
    parser.add_argument('--affinity_only',default=False,action='store_true',required=False,help="ONLY look for affinity results files")
    parser.add_argument('-2','--two_data_sources',default=False,action='store_true',required=False,help="Whether to look for 2nd data source results files")
    parser.add_argument('-t','--test_interval',type=int,default=40,required=False,help="Number of iterations between tests")
    return parser.parse_args(argv)


if __name__ == '__main__':
    args = parse_args()

    binary_class = True
    affinity = False
    if args.affinity:
        affinity = True
    if args.affinity_only:
        affinity = True
        binary_class = False

    try:
        results_files = get_results_files(args.outprefix, args.foldnums, binary_class, affinity, args.two_data_sources)
    except OSError as e:
        print "error: %s" % e
        sys.exit(1)

    if len(results_files) == 0:
        print "error: missing results files"
        sys.exit(1)

    for i in results_files:
        for key in sorted(results_files[i], key=len):
            print str(i).rjust(3), key.rjust(15), results_files[i][key]

    test_aucs, train_aucs = [], []
    test_rmsds, train_rmsds = [], []
    test_y_true, train_y_true = [], []
    test_y_score, train_y_score = [], []
    test_y_aff, train_y_aff = [], []
    test_y_predaff, train_y_predaff = [], []
    test2_aucs, train2_aucs = [], []
    test2_rmsds, train2_rmsds = [], []
    test2_y_true, train2_y_true = [], []
    test2_y_score, train2_y_score = [], []
    test2_y_aff, train2_y_aff = [], []
    test2_y_predaff, train2_y_predaff = [], []

    #read results files
    for i in results_files:

        if binary_class:
            y_true, y_score = read_results_file(results_files[i]['auc_finaltest'])
            test_y_true.extend(y_true)
            test_y_score.extend(y_score)
            y_true, y_score = read_results_file(results_files[i]['auc_finaltrain'])
            train_y_true.extend(y_true)
            train_y_score.extend(y_score)

        if affinity:
            y_aff, y_predaff = read_results_file(results_files[i]['rmsd_finaltest'])
            test_y_aff.extend(y_aff)
            test_y_predaff.extend(y_predaff)
            y_aff, y_predaff = read_results_file(results_files[i]['rmsd_finaltrain'])
            train_y_aff.extend(y_aff)
            train_y_predaff.extend(y_predaff)

        if args.two_data_sources:
            if binary_class:
                y_true, y_score = read_results_file(results_files[i]['auc_finaltest2'])
                test2_y_true.extend(y_true)
                test2_y_score.extend(y_score)
                y_true, y_score = read_results_file(results_files[i]['auc_finaltrain2'])
                train2_y_true.extend(y_true)
                train2_y_score.extend(y_score)

            if affinity:
                y_aff, y_predaff = read_results_file(results_files[i]['rmsd_finaltest2'])
                test2_y_aff.extend(y_aff)
                test2_y_predaff.extend(y_predaff)
                y_aff, y_predaff = read_results_file(results_files[i]['rmsd_finaltrain2'])
                train2_y_aff.extend(y_aff)
                train2_y_predaff.extend(y_predaff)

        #[test_auc train_auc train_loss] lr [test_rmsd train_rmsd] [[test2_auc train2_auc train2_loss] [test2_rmsd train2_rmsd]]
        out_columns = read_results_file(results_files[i]['out'])

        col_idx = 0
        if binary_class:
            test_aucs.append(out_columns[col_idx])
            train_aucs.append(out_columns[col_idx+1])
            #ignore train_loss
            col_idx += 3

        #ignore learning rate
        col_idx += 1

        if affinity:
            test_rmsds.append(out_columns[col_idx])
            train_rmsds.append(out_columns[col_idx+1])
            col_idx += 2

        if args.two_data_sources:
            if binary_class:
                test2_aucs.append(out_columns[col_idx])
                train2_aucs.append(out_columns[col_idx+1])
                #ignore train2_loss
                col_idx += 3

            if affinity:
                test2_rmsds.append(out_columns[col_idx])
                train2_rmsds.append(out_columns[col_idx+1])
                col_idx += 2

    if binary_class:
        combine_fold_results(test_aucs, train_aucs, test_y_true, test_y_score, train_y_true, train_y_score,
                             args.outprefix, args.test_interval, affinity=False, second_data_source=False)

    if affinity:
        combine_fold_results(test_rmsds, train_rmsds, test_y_aff, test_y_predaff, train_y_aff, train_y_predaff,
                             args.outprefix, args.test_interval, affinity=True, second_data_source=False,
                             filter_actives_test=test_y_true, filter_actives_train=train_y_true)

    if args.two_data_sources:
        if binary_class:
            combine_fold_results(test2_aucs, train2_aucs, test2_y_true, test2_y_score, train2_y_true, train2_y_score,
                                 args.outprefix, args.test_interval, affinity=False, second_data_source=True)

        if affinity:
            combine_fold_results(test2_rmsds, train2_rmsds, test2_y_aff, test2_y_predaff, train2_y_aff, train2_y_predaff,
                                 args.outprefix, args.test_interval, affinity=True, second_data_source=True,
                                 filter_actives_test=test2_y_true, filter_actives_train=train2_y_true)

