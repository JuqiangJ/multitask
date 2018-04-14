"""Utility functions."""

import os
import errno
import fnmatch
import pickle
import json
import numpy as np


def gen_feed_dict(model, trial, hparams):
    """Generate feed_dict for session run."""
    if hparams['in_type'] == 'normal':
        feed_dict = {model.x: trial.x,
                     model.y: trial.y,
                     model.c_mask: trial.c_mask}
    elif hparams['in_type'] == 'multi':
        n_time, batch_size = trial.x.shape[:2]
        new_shape = [n_time,
                     batch_size,
                     hparams['rule_start']*hparams['n_rule']]

        x = np.zeros(new_shape, dtype=np.float32)
        for i in range(batch_size):
            ind_rule = np.argmax(trial.x[0, i, hparams['rule_start']:])
            i_start = ind_rule*hparams['rule_start']
            x[:, i, i_start:i_start+hparams['rule_start']] = \
                trial.x[:, i, :hparams['rule_start']]

        feed_dict = {model.x: x,
                     model.y: trial.y,
                     model.c_mask: trial.c_mask}

    return feed_dict


def _contain_model_file(model_dir):
    """Check if the directory contains model files."""
    for f in os.listdir(model_dir):
        if 'model.ckpt' in f:
            return True
    return False


def valid_model_dirs(model_dir):
    """Get valid model directories given a root directory."""
    return [x[0] for x in os.walk(model_dir) if _contain_model_file(x[0])]


def load_log(train_dir):
    """Load the log file of model save_name"""
    fname = os.path.join(train_dir,'log.pkl')
    if not os.path.isfile(fname):
        return None

    with open(fname, 'rb') as f:
        log = pickle.load(f)
    return log


def save_log(log): 
    """Save the log file of model."""
    model_dir = log['train_dir']
    fname = os.path.join(model_dir, 'log.pkl')
    with open(fname,'wb') as f:
        pickle.dump(log, f)


def load_hparams(save_dir):
    """Load the hyper-parameter file of model save_name"""
    fname = os.path.join(save_dir, 'hparams.json')
    if not os.path.isfile(fname):
        return None

    with open(fname, 'rb') as f:
        hparams = json.load(f)

    # Use a different seed aftering loading,
    # since loading is typically for analysis
    hparams['rng'] = np.random.RandomState(hparams['seed']+1000)
    return hparams


def save_hparams(hparams, save_dir):
    """Save the hyper-parameter file of model save_name"""
    hparams_copy = hparams.copy()
    hparams_copy.pop('rng')  # rng can not be serialized
    with open(os.path.join(save_dir, 'hparams.json'), 'wb') as f:
        json.dump(hparams_copy, f)


def find_all_models(root_dir, hp_target):
    """Find all models that satisfy hyperparameters.

    Args:
        root_dir: root directory
        hp_target: dictionary of hyperparameters

    Returns:
        model_dirs: list of model directories
        hps: list of model hyperparameters
    """
    dirs = valid_model_dirs(root_dir)

    model_dirs = list()
    hps = list()
    for d in dirs:
        hp = load_hparams(d)
        if all(hp[key] == val for key, val in hp_target.items()):
            model_dirs.append(d)
            hps.append(hp)

    return model_dirs, hps


def find_model(root_dir, hp_target):
    """Find one model that satisfies hyperparameters.

    Args:
        root_dir: root directory
        hp_target: dictionary of hyperparameters

    Returns:
        d: model directory
        hp: model hyperparameters
    """
    model_dirs, hps = find_all_models(root_dir, hp_target)

    if not model_dirs:
        # If list empty
        print('Model not found')
        return None, None

    d = model_dirs[0]
    hp = hps[0]

    log = load_log(d)
    # check if performance exceeds target
    if log['perf_min'][-1] < hp['target_perf']:
        print('Warning: the network found did not reach target performance.')

    return d, hp


def mkdir_p(path):
    """
    Portable mkdir -p

    """
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def gen_ortho_matrix(dim, rng=None):
    """Generate random orthogonal matrix
    Taken from scipy.stats.ortho_group
    Copied here from compatibilty with older versions of scipy
    """
    H = np.eye(dim)
    for n in range(1, dim):
        if rng is None:
            x = np.random.normal(size=(dim-n+1,))
        else:
            x = rng.normal(size=(dim-n+1,))
        # random sign, 50/50, but chosen carefully to avoid roundoff error
        D = np.sign(x[0])
        x[0] += D*np.sqrt((x*x).sum())
        # Householder transformation
        Hx = -D*(np.eye(dim-n+1) - 2.*np.outer(x, x)/(x*x).sum())
        mat = np.eye(dim)
        mat[n-1:, n-1:] = Hx
        H = np.dot(H, mat)
    return H
