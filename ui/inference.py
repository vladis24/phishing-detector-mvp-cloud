"""Frozen primary inference; no fitting, alternate model selection or feature fallback."""
import json
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.validation import check_is_fitted

from dataset.schema import MODEL_FEATURE_COLUMNS, model_feature_vector

ROOT=Path(__file__).resolve().parents[1]
PRIMARY="F02_RF_A08"
THRESHOLD=.5
EXPECTED_SHA256="8ba5c2743b5f0af05b438bb629ac88dc3daba4914fe20b9bed11bd7630e5e4a0"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ModelUnavailable(ValueError): pass
class FeatureIncomplete(ValueError): pass
class FeatureSchemaMismatch(ValueError): pass


def frozen_digest(root,relative):
    provenance=json.loads((root/"output/phase11_structural_robustness/phase11_summary.json").read_text(encoding="utf-8"))
    matches=[value for path,value in provenance["source_sha256_before"].items() if path.replace("\\","/").endswith("/"+relative)]
    if len(matches)!=1 or file_hash(root/relative)!=matches[0]: raise ModelUnavailable("Frozen artifact verification failed")
    return matches[0]


def feature_order(root=ROOT):
    root=Path(root)
    relative="output/feature_ablation/feature_subsets.json"
    try:
        frozen_digest(root,relative)
        saved=json.loads((root/relative).read_text(encoding="utf-8"))
        subset=[s for s in saved if s["ablation_id"]=="A08"]
        names=subset[0]["feature_names"]
        if len(subset)!=1 or subset[0]["name"]!="A08_FULL_137" or names!=list(MODEL_FEATURE_COLUMNS) or len(names)!=137:
            raise FeatureSchemaMismatch("Authoritative A08 names/order differ")
        return names
    except FeatureSchemaMismatch: raise
    except Exception as exc: raise FeatureSchemaMismatch("Could not validate the frozen feature schema") from exc


@lru_cache(maxsize=2)
def _load_verified(root_text,digest):
    root=Path(root_text)
    model=joblib.load(root/f"output/final_test_evaluation/models/{PRIMARY}.joblib")
    metadata=json.loads((root/"output/final_test_evaluation/primary_model_result.json").read_text(encoding="utf-8"))
    if metadata["configuration_id"]!=PRIMARY or metadata["representation"]!="A08_FULL_137" or metadata["feature_count"]!=137:
        raise ModelUnavailable("Frozen primary metadata differs")
    if type(model) is not RandomForestClassifier or model.n_features_in_!=137 or len(model.classes_)!=2 or set(model.classes_)!={0,1}:
        raise ModelUnavailable("Frozen model type/classes/input differ")
    check_is_fitted(model)
    if any(model.get_params()[key]!=value for key,value in metadata["hyperparameters"].items()): raise ModelUnavailable("Frozen parameters differ")
    return model


def load_primary(root=ROOT):
    root=Path(root).resolve()
    try:
        digest=frozen_digest(root,f"output/final_test_evaluation/models/{PRIMARY}.joblib")
        if digest != EXPECTED_SHA256 or THRESHOLD != .5:
            raise ModelUnavailable("Model digest or threshold differs from deployment contract")
        frozen_digest(root,"output/final_test_evaluation/primary_model_result.json")
        return _load_verified(str(root),digest)
    except Exception as exc: raise ModelUnavailable("Could not load the verified frozen primary") from exc


@dataclass(frozen=True)
class Prediction:
    probability:float
    predicted_label:int
    title:str
    description:str
    threshold:float=THRESHOLD
    model_id:str=PRIMARY


def prediction_label(probability):
    if not np.isfinite(probability) or not 0<=probability<=1: raise ModelUnavailable("Invalid model probability")
    positive=probability>=THRESHOLD
    return Prediction(float(probability),int(positive),"Ймовірний фішинговий вебресурс" if positive else "Ймовірно легітимний вебресурс",
        "Модель класифікувала вебресурс як такий, що належить до фішингового класу." if positive else
        "Модель класифікувала вебресурс як такий, що належить до легітимного класу.")


def infer(result,root=ROOT):
    names=feature_order(root)
    try: values=model_feature_vector(result)
    except (KeyError,ValueError,TypeError,OverflowError) as exc: raise FeatureIncomplete("Incomplete/nonfinite model vector") from exc
    if len(values)!=137 or len(names)!=len(values): raise FeatureSchemaMismatch("Vector layout differs")
    model=load_primary(root)
    parameters=model.get_params(deep=True).copy()
    try:
        proba=np.asarray(model.predict_proba(np.asarray([values],dtype=np.float64)),dtype=float)
        if proba.shape!=(1,2) or not np.isfinite(proba).all() or np.any((proba<0)|(proba>1)): raise ModelUnavailable("Invalid probabilities")
        probability=float(proba[0,list(model.classes_).index(1)])
        if model.get_params(deep=True)!=parameters: raise ModelUnavailable("Model parameters mutated")
        return prediction_label(probability)
    except ModelUnavailable: raise
    except Exception as exc: raise ModelUnavailable("Frozen model inference failed") from exc
